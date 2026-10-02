"""Canonical data and content-addressed snapshots; no hidden filling of gaps."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

BAR_COLUMNS = ["symbol", "date", "raw_open", "raw_high", "raw_low", "raw_close",
               "adj_open", "adj_high", "adj_low", "adj_close", "volume", "amount"]


@dataclass
class Snapshot:
    bars: pd.DataFrame
    instruments: pd.DataFrame
    calendar: list[str]
    manifest: dict = field(default_factory=dict)
    actions: pd.DataFrame = field(default_factory=pd.DataFrame)
    market: pd.DataFrame = field(default_factory=pd.DataFrame)

    def validate(self):
        b = self.bars
        missing = set(BAR_COLUMNS) - set(b)
        if missing:
            raise ValueError(f"行情缺少字段：{sorted(missing)}")
        if b.empty or b.duplicated(["symbol", "date"]).any():
            raise ValueError("行情为空或股票日期重复")
        if not b.symbol.astype(str).str.fullmatch(r"\d{6}").all():
            raise ValueError("证券代码必须为六位字符串")
        if not b.date.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
            raise ValueError("日期必须为YYYY-MM-DD")
        pd.to_datetime(b.date,format="%Y-%m-%d",errors="raise")
        pd.to_datetime(self.calendar,format="%Y-%m-%d",errors="raise")
        for col in ("is_st","is_suspended","no_price_limit"):
            if col in b and not b[col].dropna().isin([True,False,0,1]).all():
                raise ValueError(f"{col}必须为布尔值或unknown空值")
        if not set(b.symbol).issubset(set(self.instruments.symbol)):
            raise ValueError("存在缺少证券基本信息的代码")
        required = {"symbol", "name", "exchange", "board", "list_date"}
        if not required.issubset(self.instruments.columns):
            raise ValueError("证券信息缺少市场、板块或上市日期")
        if self.instruments.symbol.duplicated().any():
            raise ValueError("证券基本信息重复")
        ins = self.instruments.set_index("symbol").loc[b.symbol.unique()]
        if not ((ins.exchange == "SSE") & (ins.board == "MAIN_A")).all():
            raise ValueError("股票池必须为已确认的上交所主板普通A股")
        if self.calendar != sorted(set(self.calendar)) or not set(b.date).issubset(self.calendar):
            raise ValueError("交易日历重复、乱序或不覆盖行情")
        for prefix in ("raw", "adj"):
            vals = b[[f"{prefix}_{x}" for x in ("open", "high", "low", "close")]]
            if not np.isfinite(vals.to_numpy(dtype=float)).all() or (vals <= 0).any().any():
                raise ValueError(f"{prefix}行情存在缺失、非正或非有限价格")
            if ((vals.iloc[:, 1] < vals.max(axis=1)) | (vals.iloc[:, 2] > vals.min(axis=1))).any():
                raise ValueError(f"{prefix}行情OHLC关系不成立")
        if not np.isfinite(b[["volume", "amount"]].to_numpy(dtype=float)).all() or (b[["volume", "amount"]] < 0).any().any():
            raise ValueError("成交量或成交额无效")
        for symbol, group in b.groupby("symbol"):
            dates = group.date.tolist()
            if dates != sorted(dates):
                raise ValueError(f"{symbol}日期乱序")
            # Leading/trailing coverage is checked against each requested experiment.
            expected = {d for d in self.calendar if dates[0] <= d <= dates[-1]}
            if expected != set(dates):
                raise ValueError(f"{symbol}存在未解释的行情缺口；请提供带停牌标志的估值记录")
        return self

    def coverage_report(self):
        rows=[]
        for symbol,g in self.bars.groupby("symbol"):
            row={"symbol":symbol,"first_date":g.date.min(),"last_date":g.date.max(),"rows":len(g)}
            for col in ("is_st","is_suspended","limit_up","limit_down"):
                row[col+"_coverage"]=float(g[col].notna().mean()) if col in g else 0.
            rows.append(row)
        return pd.DataFrame(rows)

    def check_range(self, start, end):
        dates = [d for d in self.calendar if str(start) <= d <= str(end)]
        if len(dates) < 2:
            raise ValueError("区间内交易日不足")
        for row in self.instruments.itertuples():
            b = self.bars[self.bars.symbol == row.symbol]
            delisted=getattr(row,"delist_date",None)
            last=str(delisted) if pd.notna(delisted) and delisted else "9999-12-31"
            needed = [d for d in dates if str(row.list_date)<=d<=last]
            if needed and (b.empty or b.date.min() > needed[0] or b.date.max() < needed[-1]):
                raise ValueError(f"{row.symbol}未覆盖完整请求区间；退市不能按最后价自动清仓")
        return dates

    def digest(self):
        parts = [self.bars.to_csv(index=False), self.instruments.to_csv(index=False),
                 json.dumps(self.calendar), self.actions.to_csv(index=False),
                 json.dumps({k:v for k,v in self.manifest.items() if k != "snapshot_id"}, sort_keys=True, ensure_ascii=False)]
        if not self.market.empty:
            parts.append(self.market.to_csv(index=False))
        return sha256("\n".join(parts).encode()).hexdigest()

    def save(self, root="storage/snapshots"):
        self.validate()
        digest = self.digest()
        path = Path(root) / digest[:16]
        path.mkdir(parents=True, exist_ok=True)
        self.bars.to_parquet(path / "bars.parquet", index=False)
        self.instruments.to_parquet(path / "instruments.parquet", index=False)
        self.actions.to_parquet(path / "actions.parquet", index=False)
        self.market.to_parquet(path / "market.parquet", index=False)
        (path / "calendar.json").write_text(json.dumps(self.calendar), encoding="utf-8")
        (path / "manifest.json").write_text(json.dumps({**self.manifest, "snapshot_id": digest}, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path):
        p = Path(path)
        s = cls(pd.read_parquet(p / "bars.parquet"), pd.read_parquet(p / "instruments.parquet"),
                json.loads((p / "calendar.json").read_text()),
                json.loads((p / "manifest.json").read_text(encoding="utf-8")), pd.read_parquet(p / "actions.parquet"),
                pd.read_parquet(p / "market.parquet") if (p/"market.parquet").exists() else pd.DataFrame())
        if s.digest() != s.manifest["snapshot_id"]:
            raise ValueError("数据快照校验失败，文件可能被修改")
        return s.validate()
