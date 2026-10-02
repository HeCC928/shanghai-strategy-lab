import numpy as np
import pandas as pd

from lab.config import Config
from lab.data import Snapshot


def compute_features(snapshot: Snapshot, c: Config) -> pd.DataFrame:
    out = []
    cal = np.array(snapshot.calendar)
    meta = snapshot.instruments.set_index("symbol")
    for symbol, frame in snapshot.bars.groupby("symbol", sort=True):
        f = frame.copy().reset_index(drop=True)
        p = f.adj_close
        r = p.pct_change(fill_method=None)
        f["momentum"] = p / p.shift(c.momentum_window) - 1
        f["volatility"] = r.rolling(c.vol_window).std(ddof=1)
        f["low_volatility"] = r.rolling(c.low_vol_window).std(ddof=1) * np.sqrt(252)
        f["short_ma"] = p.rolling(c.short_ma).mean()
        f["long_ma"] = p.rolling(c.long_ma).mean()
        f["prior_high"] = p.shift().rolling(c.breakout_window).max()
        f["breakout"] = p / f.prior_high - 1
        f["amount_ratio"] = f.amount / f.amount.shift().rolling(20).mean().replace(0, np.nan)
        f["reversal"] = p / p.shift(c.reversal_window) - 1
        f["deviation"] = p / p.rolling(c.threshold_ma).mean() - 1
        f["cross_up"] = (f.deviation > c.entry_threshold) & (f.deviation.shift() <= c.entry_threshold)
        f["avg_amount"] = f.amount.rolling(20).mean()
        f["prior_avg_amount"] = f.avg_amount.shift()
        listed = np.searchsorted(cal, str(meta.loc[symbol, "list_date"]))
        f["listing_age"] = np.searchsorted(cal, f.date) - listed + 1
        f["history_count"] = np.arange(1, len(f) + 1)
        f["eligible"] = (f.listing_age >= c.min_history) & (f.history_count >= c.min_history) & (f.avg_amount >= c.min_amount)
        f["reason"] = "通过共同过滤"
        f.loc[(f.listing_age < c.min_history) | (f.history_count < c.min_history), "reason"] = "上市或历史长度不足"
        f.loc[f.avg_amount.isna() | (f.avg_amount < c.min_amount), "reason"] = "流动性或成交额历史不足"
        if "delist_date" in meta:
            delisted=meta.loc[symbol,"delist_date"]
            if pd.notna(delisted) and delisted:
                f.loc[f.date>=str(delisted),"eligible"]=False
                f.loc[f.date>=str(delisted),"reason"]="已到退出日期"
        if c.exclude_st:
            if "is_st" not in f or f.is_st.isna().any():
                raise ValueError("历史ST状态不完整，不能启用ST过滤")
            f.loc[f.is_st.astype(bool), "eligible"] = False
            f.loc[f.is_st.astype(bool), "reason"] = "历史ST过滤"
        f["score"] = np.nan
        condition = pd.Series(True, index=f.index)
        if c.strategy == "threshold":
            f["score"] = f.deviation
            condition = f.deviation > c.entry_threshold
        elif c.strategy == "momentum":
            f["score"] = f.momentum / f.volatility.replace(0, np.nan)
            condition = (f.momentum > 0) & (p > f.short_ma) & (f.short_ma > f.long_ma)
        elif c.strategy == "low_vol":
            f["score"] = -f.low_volatility
        elif c.strategy == "breakout":
            f["score"] = f.breakout
            condition = (f.breakout > 0) & (f.amount_ratio >= c.amount_multiple)
        elif c.strategy == "reversal":
            f["score"] = -f.reversal
            condition = (f.reversal < 0) & (p > f.long_ma)
        else:
            f["score"] = 0.
        valid = condition & np.isfinite(f.score)
        f.loc[f.eligible & ~valid, "reason"] = "策略条件不满足或指标不足"
        f["qualified"] = f.eligible & valid
        out.append(f)
    return pd.concat(out, ignore_index=True)


def rank_candidates(day: pd.DataFrame) -> pd.DataFrame:
    f = day.sort_values(["qualified", "score", "symbol"], ascending=[False, False, True], kind="stable").copy()
    f["rank"] = pd.array([None] * len(f), dtype="Int64")
    f.loc[f.qualified, "rank"] = range(1, int(f.qualified.sum()) + 1)
    return f
