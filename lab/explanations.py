import pandas as pd


def explain_decision(row,c):
    def percent(name):
        value=row.get(name)
        return "数据不足" if pd.isna(value) else f"{value:.2%}"
    reason=row.get("reason","")
    if c.strategy=="threshold":
        text=f"收盘价相对{c.threshold_ma}日均线偏离{percent('deviation')}；入场线{c.entry_threshold:.1%}，退出线{c.exit_threshold:.1%}。"
    elif c.strategy=="momentum":
        text=f"{c.momentum_window}日收益{percent('momentum')}，{c.vol_window}日日收益波动{percent('volatility')}。"
    elif c.strategy=="low_vol":
        text=f"{c.low_vol_window}日年化波动{percent('low_volatility')}；波动较低者优先。"
    elif c.strategy=="breakout":
        ratio=row.get('amount_ratio')
        text=f"相对前期高点突破幅度{percent('breakout')}；成交额倍数{ratio:.2f}，门槛{c.amount_multiple:.2f}。" if pd.notna(ratio) else "突破或成交额历史不足。"
    else:
        text=f"过去{c.reversal_window}日收益{percent('reversal')}，并检查中期趋势条件。"
    rank=row.get("rank")
    ranking=f"排名第{int(rank)}；" if pd.notna(rank) else "未进入有效排名；"
    return text+ranking+f"目标权重{row.get('target_weight',0):.1%}。{reason}。实际是否成交以订单记录为准。"


LABELS={"symbol":"股票代码","date":"日期","signal_date":"信号日期","execution_date":"最早执行日",
        "origin_signal_date":"原始信号日","score":"得分","rank":"排名","qualified":"条件通过",
        "reason":"原因","target_weight":"目标权重","momentum":"动量收益","volatility":"日波动",
        "low_volatility":"年化波动","deviation":"均线偏离","cross_up":"本日上穿","amount_ratio":"成交额倍数",
        "breakout":"突破幅度","reversal":"短期收益","avg_amount":"20日平均成交额",
        "side":"方向","quantity":"份额／股数","price":"成交价","amount":"成交额（元）","fees":"费用（元）",
        "order_id":"订单编号","plan_id":"建仓计划","stage":"批次","status":"状态","reject_reason":"未成交原因",
        "cash":"现金","value":"市值","weight":"实际权重","sellable_quantity":"可售股数","mark":"估值价",
        "budget":"计划本金","spent":"已投入","closed_at":"计划结束日","attempts":"本批尝试次数"}


def localized(frame):
    f=frame.copy()
    if "side" in f: f["side"]=f.side.replace({"buy":"买入","sell":"卖出"})
    if "status" in f: f["status"]=f.status.replace({"active":"进行中","completed":"完成","filled":"成交","rejected":"未成交"})
    return f.rename(columns=LABELS)


METRIC_LABELS={"total_return":"累计收益","cagr":"年化收益CAGR","volatility":"年化波动","sharpe":"Sharpe",
"max_drawdown":"最大回撤（水下收益）","drawdown_peak":"回撤起点","drawdown_trough":"回撤谷底","fees":"累计费用（元）",
"slippage_loss":"估计滑点（元）","fills":"成交笔数","rejected_orders":"拒绝笔数","win_rate":"已平仓胜率","closed_lots":"已平仓匹配批次",
"average_holding_days":"平均持有天数","turnover":"单边年化换手","average_cash_weight":"平均现金比例","annual_excess":"年化超额（小数）",
"final_largest_weight":"期末最大单票权重","final_top5_weight":"期末前5权重","final_cash_weight":"期末现金比例","unrealized_pnl":"未实现收益（元）",
"short_period":"不足一年","sharpe_na_reason":"Sharpe缺失原因","win_rate_na_reason":"胜率缺失原因"}
