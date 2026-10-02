from collections import defaultdict, deque

import numpy as np
import pandas as pd


def calculate_metrics(result):
    e, fills, c = result.equity, result.fills, result.config
    v = e.equity
    r = v.pct_change(fill_method=None).dropna()
    elapsed = (pd.Timestamp(e.date.iloc[-1]) - pd.Timestamp(e.date.iloc[0])).days
    total = float(v.iloc[-1]/v.iloc[0]-1)
    cagr = float((1+total)**(365.25/elapsed)-1) if elapsed > 0 else None
    excess = r - ((1+c.risk_free)**(1/252)-1)
    std = excess.std(ddof=1)
    sharpe = float(np.sqrt(252)*excess.mean()/std) if pd.notna(std) and std > 1e-12 else None
    dd = v/v.cummax()-1
    trough = int(dd.idxmin())
    peak = int(v.iloc[:trough+1].idxmax())
    wins, closed, holding_days = 0, 0, []
    lots = defaultdict(deque)
    for fill in fills.itertuples():
        if fill.side == "buy":
            lots[fill.symbol].append([fill.quantity, (fill.amount+fill.fees)/fill.quantity, fill.date])
        else:
            remaining = fill.quantity
            proceeds = (fill.amount-fill.fees)/fill.quantity
            while remaining > 1e-8 and lots[fill.symbol]:
                lot = lots[fill.symbol][0]
                q = min(remaining, lot[0])
                closed += 1
                wins += int(proceeds > lot[1])
                holding_days.append((pd.Timestamp(fill.date)-pd.Timestamp(lot[2])).days)
                lot[0] -= q
                remaining -= q
                if lot[0] < 1e-8:
                    lots[fill.symbol].popleft()
    prior = e.assign(prior=e.equity.shift()).set_index("date").prior
    if c.mode=="shares":
        closed = len(result.closed_lots)
        wins = int((result.closed_lots.pnl>0).sum()) if closed else 0
        holding_days = [(pd.Timestamp(x.date)-pd.Timestamp(x.bought_on)).days for x in result.closed_lots.itertuples()]
    final_positions=result.positions[result.positions.date==e.date.iloc[-1]]
    final_marks=dict(zip(final_positions.symbol,final_positions.get("mark",pd.Series(dtype=float))))
    unrealized=sum(q*(final_marks[s]-cost) for s,entries in lots.items() for q,cost,_ in entries if q>1e-8 and s in final_marks) if c.mode!="shares" else None
    turnover = float(sum(f.amount/prior.loc[f.date] for f in fills.itertuples())*.5*252/len(r)) if len(r) else None
    return {
        "total_return": total, "cagr": cagr, "sharpe": sharpe,
        "volatility": float(r.std(ddof=1)*np.sqrt(252)) if len(r)>1 else None,
        "max_drawdown": float(dd.min()), "drawdown_peak": e.date.iloc[peak], "drawdown_trough": e.date.iloc[trough],
        "fees": float(fills.fees.sum()), "slippage_loss": float(fills.slippage_loss.sum()),
        "fills": len(fills), "rejected_orders": int((result.orders.status == "rejected").sum()),
        "win_rate": wins/closed if closed else None, "closed_lots": closed,
        "average_holding_days": float(np.mean(holding_days)) if holding_days else None,
        "turnover": turnover, "average_cash_weight": float((e.cash/e.equity).iloc[1:].mean()),
        "final_largest_weight": float(final_positions.weight.max()) if len(final_positions) else 0.,
        "final_top5_weight": float(final_positions.weight.nlargest(5).sum()) if len(final_positions) else 0.,
        "final_cash_weight": float(e.cash.iloc[-1]/v.iloc[-1]),
        "unrealized_pnl": unrealized,
        "short_period": elapsed < 365, "sharpe_na_reason": "日超额收益标准差为零或样本不足" if sharpe is None else "",
        "win_rate_na_reason": "没有已平仓匹配批次" if not closed else "",
    }


def monthly_returns(equity):
    r = equity.set_index(pd.to_datetime(equity.date)).equity.pct_change(fill_method=None).dropna()
    monthly = (1+r).groupby(r.index.to_period("M")).prod()-1
    return pd.DataFrame({"year": monthly.index.year, "month": monthly.index.month, "return": monthly.values})


def period_metrics(equity,start,end,risk_free=0.):
    """Use the close before the first selected day as the interval cost basis."""
    chosen=equity[(equity.date>=str(start))&(equity.date<=str(end))&(~equity.initial)]
    if chosen.empty:raise ValueError("所选区间没有交易日")
    before=equity[equity.date<chosen.date.iloc[0]].tail(1)
    if before.empty:raise ValueError("缺少区间起点前净值")
    frame=pd.concat([before,chosen])
    value=frame.equity
    returns=value.pct_change(fill_method=None).dropna()
    total=float(value.iloc[-1]/value.iloc[0]-1)
    days=(pd.Timestamp(frame.date.iloc[-1])-pd.Timestamp(frame.date.iloc[0])).days
    excess=returns-((1+risk_free)**(1/252)-1)
    std=excess.std(ddof=1)
    return {"估值起点":frame.date.iloc[0],"截止":frame.date.iloc[-1],"区间收益":total,
            "年化收益":float((1+total)**(365.25/days)-1),"最大回撤损失":float(-(value/value.cummax()-1).min()),
            "Sharpe":float(252**.5*excess.mean()/std) if pd.notna(std) and std>1e-12 else None,
            "交易日数":len(returns)}
