"""An experiment and its fixed, pre-declared comparator portfolios."""
from time import perf_counter

import pandas as pd

from lab.config import Config
from lab.engine import run_backtest


def run_experiment(config, snapshot, progress=None, parameter_schedule=None, feature_cache=None):
    start = perf_counter()
    names = [(config.strategy, "策略"), ("buy_hold", "同池买入持有"), ("equal_weight", "同池等权调仓")]
    results = []
    for index, (strategy, label) in enumerate(names):
        params = {**config.model_dump(), "strategy": strategy}
        if index:
            params.update(exposure=1., market_filter=False, volatility_control=False)
        c = Config(**params)
        callback = (lambda value, text, i=index, n=label: progress((i+value)/3, n+" · "+text)) if progress else None
        results.append(run_backtest(c, snapshot, callback, parameter_schedule=parameter_schedule if index==0 else None, feature_cache=feature_cache))
    r = results[0]
    r.benchmarks = pd.DataFrame({"date": r.equity.date, "buy_hold": results[1].equity.equity,
                                 "equal_weight": results[2].equity.equity})
    r.benchmark_metrics = {key: x.metrics for key, x in zip(["buy_hold", "equal_weight"], results[1:])}
    if not snapshot.market.empty:
        market=snapshot.market.set_index("date").close.reindex(r.equity.date)
        if market.isna().any():
            r.manifest["limitations"].append("上证综指未覆盖完整实验区间，未画不完整参考曲线")
        else:
            r.benchmarks["market"]=market.to_numpy()/market.iloc[0]*config.capital
    r.metrics["annual_excess"] = r.metrics["cagr"]-results[1].metrics["cagr"] if r.metrics["cagr"] is not None and results[1].metrics["cagr"] is not None else None
    r.manifest["benchmark_policy"] = "固定同池买入持有与等权调仓；相同日期、初始资金、记账、费用、滑点及分批/每日额度。买入持有在区间开始前确定候选，此后不再选股。"
    r.timings["experiment_seconds"] = perf_counter()-start
    return r
