"""Network access is confined to explicit downloads. Successful requests are cached."""
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import time
from functools import wraps
from filelock import FileLock

import pandas as pd

from lab.data import Snapshot


class DownloadError(RuntimeError):
    pass


def serialized_network(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        lock=Path(__file__).resolve().parents[1]/"storage"/"provider.lock"
        lock.parent.mkdir(parents=True,exist_ok=True)
        # Anonymous BaoStock logins can invalidate another session; serialize sources.
        with FileLock(lock,timeout=1):
            return function(*args,**kwargs)
    return wrapped


def _query(result):
    if result.error_code != "0":
        raise DownloadError(f"BaoStock {result.error_code}: {result.error_msg}")
    rows = []
    # BaoStock get_data() still calls DataFrame.append on paginated responses.
    # Iterate the documented cursor instead; compatible with pandas 2.x.
    while result.next():
        rows.append(result.get_row_data())
    if result.error_code != "0":
        raise DownloadError(f"BaoStock分页失败 {result.error_code}: {result.error_msg}")
    return pd.DataFrame(rows, columns=result.fields)


@serialized_network
def download_snapshot(symbols=None, count=12, start="2017-01-01", end="2025-03-07",
                      source="akshare", root="storage/downloads", progress=None):
    import akshare as ak
    import baostock as bs

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    master_path = root / "sse_main_instruments.csv"
    if master_path.exists():
        master = pd.read_csv(master_path, dtype=str)
    else:
        raw = ak.stock_info_sh_name_code(symbol="主板A股")
        raw.to_csv(root / "sse_master_raw.csv", index=False, encoding="utf-8-sig")
        master = raw.rename(columns={"证券代码": "symbol", "证券简称": "name", "上市日期": "list_date"})
        master["symbol"] = master.symbol.astype(str).str.zfill(6)
        master["list_date"] = master.list_date.astype(str)
        master["exchange"], master["board"] = "SSE", "MAIN_A"
        master = master[["symbol", "name", "list_date", "exchange", "board"]]
        master.to_csv(master_path, index=False)
    if symbols:
        unknown = set(symbols)-set(master.symbol)
        if unknown:
            raise DownloadError(f"当前上交所主板A股名单无法验证以下代码：{sorted(unknown)}；退市观察池请导入完整CSV")
        instruments = master[master.symbol.isin(symbols)].sort_values("symbol")
    else:
        # Deterministic CURRENT observation pool, never presented as a historical universe.
        instruments = master[master.list_date < start].sort_values("symbol").head(count)
    logged = bs.login()
    if logged.error_code != "0":
        raise DownloadError(f"交易日历连接失败：{logged.error_msg}")
    bars, failures, traces = [], [], []
    try:
        calendar_frame = _query(bs.query_trade_dates(start_date=start, end_date=end))
        calendar_frame.to_csv(root / f"calendar_{start}_{end}.csv", index=False)
        calendar = calendar_frame.loc[calendar_frame.is_trading_day == "1", "calendar_date"].tolist()
        for index, ins in enumerate(instruments.itertuples()):
            cache = root / f"{source}_{ins.symbol}_{start}_{end}.parquet"
            try:
                if cache.exists():
                    frame = pd.read_parquet(cache)
                else:
                    frame = None
                    for attempt in range(3):
                        try:
                            frame = _ak_bars(ak, bs, ins.symbol, start, end, root) if source == "akshare" else _bs_bars(bs, ins.symbol, start, end, root)
                            break
                        except Exception as exc:
                            if attempt == 2:
                                raise
                            if "10001001" in str(exc):
                                response=bs.login()
                                if response.error_code!="0": raise DownloadError(response.error_msg)
                            time.sleep(1+attempt)
                    temp=cache.with_suffix(".parquet.tmp")
                    frame.to_parquet(temp,index=False)
                    temp.replace(cache)
                bars.append(frame)
                traces.append({"symbol": ins.symbol, "cache": cache.name, "rows": len(frame)})
            except Exception as exc:
                failures.append({"symbol": ins.symbol, "error": str(exc)})
            if progress:
                progress((index+1)/len(instruments), f"下载 {index+1}/{len(instruments)} {ins.symbol}")
            time.sleep(.15)
    finally:
        bs.logout()
    report = {"source": source, "requested": len(instruments), "succeeded": len(bars), "failures": failures,
              "fetched_at": datetime.now(timezone.utc).isoformat(), "requests": traces}
    (root / "last_download_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures:
        raise DownloadError(f"{len(failures)}只股票下载失败。成功部分已缓存，重试会复用；详情见数据下载记录。未创建不完整快照。")
    if not bars:
        raise DownloadError("没有符合条件的股票")
    snapshot = Snapshot(pd.concat(bars, ignore_index=True), instruments.reset_index(drop=True), calendar,
                        {**report, "label": f"真实行情 · {source} · 固定观察池{len(instruments)}只", "schema_version": 1,
                         "package_versions": {p: version(p) for p in ("akshare", "baostock", "pandas")},
                         "adjustment": "qfq", "start": start, "end": end,
                         "limitations": ["当前存续主板股票按代码选取的固定观察池，存在幸存者和事后选择偏差", "历史涨跌停限制价与公司行动到账事件未补齐", "仅供本地研究，原始行情不默认授权再分发"]})
    snapshot.validate()
    return snapshot


def _status(bs, symbol, start, end):
    frame = _query(bs.query_history_k_data_plus("sh."+symbol, "date,tradestatus,isST", start_date=start, end_date=end))
    return frame.rename(columns={"tradestatus": "trade_status", "isST": "is_st"})


def _ak_bars(ak, bs, symbol, start, end, root):
    pieces = []
    for adjustment, prefix in [("", "raw"), ("qfq", "adj")]:
        raw = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start.replace("-", ""),
                                 end_date=end.replace("-", ""), adjust=adjustment, timeout=20)
        if raw.empty:
            raise DownloadError(f"{symbol}东方财富无行情")
        raw.to_csv(root / f"raw_ak_{symbol}_{prefix}_{start}_{end}.csv", index=False, encoding="utf-8-sig")
        f = raw.rename(columns={"日期": "date", "开盘": f"{prefix}_open", "最高": f"{prefix}_high",
                                "最低": f"{prefix}_low", "收盘": f"{prefix}_close", "成交量": "volume", "成交额": "amount"})
        f["date"] = f.date.astype(str)
        fields = ["date"] + [f"{prefix}_{k}" for k in ("open", "high", "low", "close")]
        if prefix == "raw":
            f["volume"] = f.volume*100  # Eastmoney daily volume is in lots.
            fields += ["volume", "amount"]
        pieces.append(f[fields])
    f = pieces[0].merge(pieces[1], on="date", how="outer", validate="one_to_one")
    status = _status(bs, symbol, start, end)
    status.to_csv(root / f"raw_status_{symbol}_{start}_{end}.csv", index=False)
    f = _merge_status(f, status)
    f["symbol"] = symbol
    return f.sort_values("date").reset_index(drop=True)


def _bs_bars(bs, symbol, start, end, root):
    pieces = []
    for adjustment, prefix in [("3", "raw"), ("2", "adj")]:
        raw = _query(bs.query_history_k_data_plus("sh."+symbol, "date,open,high,low,close,volume,amount,tradestatus,isST",
                                                start_date=start, end_date=end, frequency="d", adjustflag=adjustment))
        raw.to_csv(root / f"raw_bs_{symbol}_{prefix}_{start}_{end}.csv", index=False)
        f = raw.rename(columns={k: f"{prefix}_{k}" for k in ("open", "high", "low", "close")})
        fields = ["date"] + [f"{prefix}_{k}" for k in ("open", "high", "low", "close")]
        if prefix == "raw":
            fields += ["volume", "amount"]
        for col in fields[1:]:
            f[col] = pd.to_numeric(f[col], errors="coerce")
        pieces.append(f[fields])
    f = pieces[0].merge(pieces[1], on="date", how="outer", validate="one_to_one")
    f = _merge_status(f, raw[["date", "tradestatus", "isST"]].rename(columns={"tradestatus": "trade_status", "isST": "is_st"}))
    f["symbol"] = symbol
    return f.sort_values("date").reset_index(drop=True)


def _merge_status(frame, status):
    f = frame.merge(status, on="date", how="outer", validate="one_to_one").sort_values("date")
    f["is_suspended"] = f.trade_status.map({"0": True, "1": False}).astype("boolean")
    f["is_st"] = f.is_st.map({"0": False, "1": True}).astype("boolean")
    # Only explicitly documented suspension dates may carry forward valuation.
    for prefix in ("raw", "adj"):
        previous = f[f"{prefix}_close"].where(f[f"{prefix}_close"] > 0).ffill()
        for k in ("open", "high", "low", "close"):
            col = f"{prefix}_{k}"
            mask = f.is_suspended.fillna(False) & (f[col].isna() | (f[col] <= 0))
            f.loc[mask, col] = previous[mask]
    for col in ("volume", "amount"):
        f.loc[f.is_suspended.fillna(False) & f[col].isna(), col] = 0.
    return f.drop(columns="trade_status")


@serialized_network
def attach_market(snapshot):
    import baostock as bs
    root=Path("storage/downloads")
    root.mkdir(parents=True,exist_ok=True)
    cache=root/f"sse_index_{snapshot.calendar[0]}_{snapshot.calendar[-1]}.csv"
    if cache.exists():
        frame=pd.read_csv(cache,dtype={"date":str})
    else:
        response=bs.login()
        if response.error_code!="0": raise DownloadError(response.error_msg)
        try:
            frame=_query(bs.query_history_k_data_plus("sh.000001","date,close",start_date=snapshot.calendar[0],end_date=snapshot.calendar[-1],frequency="d",adjustflag="3"))
            frame["close"]=pd.to_numeric(frame.close,errors="raise")
            frame.to_csv(cache,index=False)
        finally: bs.logout()
    if frame.date.duplicated().any() or (frame.close<=0).any(): raise DownloadError("上证综指行情异常")
    snapshot.market=frame
    snapshot.manifest.pop("snapshot_id",None)
    snapshot.manifest["market_reference"]="BaoStock 上证综指（价格指数，不含分红，不是可直接投资的同口径基准）"
    return snapshot
