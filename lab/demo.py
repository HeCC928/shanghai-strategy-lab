"""Explicitly synthetic, seeded OHLC sample for offline UI and accounting demos."""
import numpy as np
import pandas as pd

from lab.data import Snapshot


def synthetic_snapshot(count=12, start="2017-01-02", end="2025-03-07"):
    dates = pd.bdate_range(start, end).strftime("%Y-%m-%d").tolist()
    rng = np.random.default_rng(20260913)
    bars, instruments = [], []
    for i in range(count):
        symbol = f"{600000+i:06d}"
        instruments.append({"symbol": symbol, "name": f"合成样本{i+1:02d}", "exchange": "SSE", "board": "MAIN_A", "list_date": dates[0]})
        n = len(dates)
        cycles = .0015*np.sin(np.arange(n)/45+i)
        close = (10+i*2)*np.exp(np.cumsum(rng.normal(.00015, .012, n)+cycles))
        opening = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, .003, n))
        high = np.maximum(opening, close)*(1+rng.uniform(.001, .015, n))
        low = np.minimum(opening, close)*(1-rng.uniform(.001, .015, n))
        amount = rng.lognormal(np.log(1e8), .5, n)
        f = pd.DataFrame({"symbol": symbol, "date": dates, "amount": amount, "volume": amount/close,
                          "is_st": False, "is_suspended": False})
        for prefix in ("raw", "adj"):
            for field, values in [("open", opening), ("high", high), ("low", low), ("close", close)]:
                f[f"{prefix}_{field}"] = values
        bars.append(f)
    return Snapshot(pd.concat(bars, ignore_index=True), pd.DataFrame(instruments), dates,
                    {"source": "synthetic", "label": "离线合成数据演示（非真实股票收益）", "seed": 20260913,
                     "limitations": ["合成价格与工作日日历仅用于功能演示，不作为投资研究结果", "固定观察池模式"]}).validate()
