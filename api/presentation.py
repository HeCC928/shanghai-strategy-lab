"""Read-only presentation models. Research artifacts remain immutable."""
import json
import re
from pathlib import Path

import pandas as pd

NAMES = {"threshold": "Threshold", "momentum": "Trend momentum", "low_vol": "Low volatility",
         "breakout": "Volume breakout", "reversal": "Short-term reversal",
         "buy_hold": "Buy & hold", "equal_weight": "Equal-weight rebalance"}
EVENTS = {
    "分批条件复查通过": "Scheduled entry tranche executed",
    "跌破退出阈值": "Price deviation fell below the exit threshold",
    "调仓目标减仓": "Position reduced to the new allocation",
    "计划到期": "Plan expired", "退出条件触发": "Exit condition triggered",
    "新目标移除": "Removed from the new allocation", "目标减仓": "Allocation reduced",
    "超过尝试次数": "Maximum execution attempts reached", "无当日行情": "No quote for this session",
    "停牌": "Trading suspended", "开盘涨停": "Opening price at the upper limit",
    "开盘跌停": "Opening price at the lower limit", "滑点后价格超过涨停限制": "Slipped price exceeds the upper limit",
    "滑点后价格低于跌停限制": "Slipped price exceeds the lower limit",
    "历史成交额容量不足": "Insufficient trailing liquidity", "单日新增买入额度用尽": "Daily purchase cap reached",
    "现金不足": "Insufficient cash", "现金不足以支付一手及费用": "Cash below one lot plus fees",
    "本批预算或容量不足一手": "Tranche budget or liquidity below one lot",
    "T+1或股份到账限制，无可售股数": "No sellable shares under T+1 or settlement restrictions",
    "减仓预算或容量不足合法卖出单位": "Reduction below a valid sale lot", "可执行预算不足": "Insufficient executable budget",
    "通过共同过滤": "Passed universe and liquidity filters",
    "满足条件但未入选／未发生入场上穿／持仓名额不足": "Eligible, but no new entry crossing or no allocation slot",
    "有记录的退出现金回收": "Recorded delisting cash recovery",
    "上市或历史长度不足": "Insufficient listing or price history",
    "流动性或成交额历史不足": "Insufficient liquidity or trading amount history",
    "已到退出日期": "Security has reached its exit date",
    "历史ST过滤": "Excluded by historical ST status",
    "策略条件不满足或指标不足": "Strategy conditions not met or indicators unavailable",
}


def english(value):
    if not isinstance(value, str):
        return value
    if value in EVENTS:
        return EVENTS[value]
    return "Recorded research event" if re.search(r"[\u4e00-\u9fff]", value) else value


def records(frame):
    frame = frame.copy()
    for col in ("reason", "reject_reason", "status"):
        if col in frame:
            frame[col] = frame[col].map(english)
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=12))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summary(path):
    c, m = read_json(path / "config.json"), read_json(path / "manifest.json")
    return {"id": path.name, "name": NAMES.get(c["strategy"], c["strategy"]), "config": c,
            "metrics": read_json(path / "metrics.json"), "source": m.get("source", "unknown"),
            "snapshot_id": m.get("snapshot_id", "")[:16], "created_at": m.get("created_at"),
            "universe_size": m.get("requested"), "study": m.get("study", "Fixed-parameter research"),
            "target_period": c["start"] == "2025-07-01" and c["end"] == "2026-06-30",
            "optimized": m.get("target_period_optimized", False)}


def limitations(config, manifest):
    items = ["Fixed observation pool: current surviving stocks; survivorship and selection bias remain.",
             "Daily close signals; execution attempted at the next session open.",
             "Saved results include configured fees and slippage. No live orders are sent."]
    if config["mode"] == "research":
        items.append("Adjusted-price research uses fractional units and omits minimum commissions and transfer fees. Historical price limits and cash dividend settlement are incomplete; this is not a fully validated share ledger.")
    else:
        items.append("Share ledger uses imported corporate actions and T+1 availability; intraday queue priority is not simulated.")
    if manifest.get("target_period_optimized"):
        items.append("This case was selected after exploring the target period. It is not an independent holdout test.")
    return items
