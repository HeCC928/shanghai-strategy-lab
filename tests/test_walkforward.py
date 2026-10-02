import json
import pandas as pd
import pytest

from lab.config import Config
from lab.demo import synthetic_snapshot
from lab.engine import run_backtest
from lab.protocols import WalkForwardConfig
from lab.risk import risk_history
from lab.walkforward import run_walkforward
from lab.store import save_result, load_result


def fixture():
    snapshot = synthetic_snapshot(2, "2023-01-02", "2024-06-28")
    snapshot.manifest["end"] = "2024-06-30"
    config = Config(strategy="low_vol", start="2024-05-01", end="2024-06-30", min_history=20,
                    top_n=2, max_weight=.5, min_amount=0, low_vol_window=20)
    protocol = WalkForwardConfig(start="2024-05-01",end="2024-06-30",train_months=6,validation_months=2,shortlist=2,max_drawdown=1)
    return snapshot, config, protocol


def test_month_windows_and_previous_close():
    s,c,p=fixture()
    w=p.windows(s.calendar)
    assert w[0]["train_start"] == "2023-09-01"
    assert w[0]["validation_start"] == "2024-03-01"
    assert w[0]["signal_date"] == "2024-04-30"
    assert w[1]["signal_date"] == "2024-05-31"
    assert all(x["validation_end"]<x["replay_start"] for x in w)


def test_same_parameters_preserve_tranches_and_ledger():
    s,c,p=fixture()
    expected=run_backtest(c,s)
    schedule=[{"signal_date":w["signal_date"],"params":{"low_vol_window":20}} for w in p.windows(s.calendar)]
    actual=run_backtest(c,s,parameter_schedule=schedule)
    pd.testing.assert_frame_equal(expected.equity,actual.equity)
    pd.testing.assert_frame_equal(expected.fills,actual.fills)
    assert actual.equity.initial.sum()==1


def test_cash_switch_sells_existing_holdings_after_cutoff():
    s,c,p=fixture()
    actual=run_backtest(c,s,parameter_schedule=[{"signal_date":"2024-05-31","params":{"exposure":0.}}])
    before=actual.positions[actual.positions.date=="2024-05-30"]
    assert before.value.sum()>0
    sell=actual.fills[(actual.fills.date=="2024-06-03")&(actual.fills.side=="sell")]
    assert len(sell)>0 and (sell.signal_date=="2024-05-31").all()
    assert actual.positions[actual.positions.date=="2024-06-28"].empty
    assert actual.equity.cash.iloc[-1] == pytest.approx(actual.equity.equity.iloc[-1])


def test_rolling_selection_cannot_see_replay_prices(tmp_path):
    s,c,p=fixture()
    candidates=[{"low_vol_window":20},{"low_vol_window":40}]
    before=run_walkforward(c,s,p,candidates)
    cols=[x for x in s.bars if x.startswith(("raw_","adj_"))]
    s.bars.loc[s.bars.date>="2024-05-15",cols] *= 1.5
    after=run_walkforward(c,s,p,candidates)
    assert before.windows[0]["selected_params"]==after.windows[0]["selected_params"]
    assert before.windows[0]["validation_candidates"]==after.windows[0]["validation_candidates"]
    pd.testing.assert_frame_equal(before.equity[before.equity.date<"2024-05-15"],after.equity[after.equity.date<"2024-05-15"])
    # Metrics derive from the continuous daily path, never an average of folds.
    returns=before.equity.equity.pct_change().dropna()
    assert before.metrics["sharpe"]==pytest.approx(252**.5*returns.mean()/returns.std(ddof=1))
    path=save_result(before,tmp_path)
    restored=load_result(path)
    assert len(restored.windows)==2
    assert len(restored.selection_trials)==8
    assert restored.manifest["parameter_schedule"]==before.manifest["parameter_schedule"]


def test_risk_history_is_causal_and_requires_market_data():
    s,c,p=fixture()
    c=Config(**{**c.model_dump(),"market_filter":True,"volatility_control":True})
    with pytest.raises(ValueError,match="Market reference"):
        risk_history(s,c)
    s.market=s.bars[s.bars.symbol=="600000"][["date","adj_close"]].rename(columns={"adj_close":"close"})
    before=risk_history(s,c)
    s.market.loc[s.market.date>"2024-05-01","close"] *= 2
    after=risk_history(s,c)
    pd.testing.assert_frame_equal(before[before.date<="2024-05-01"],after[after.date<="2024-05-01"])
    assert after.target_exposure.between(0,1).all()


def test_no_eligible_candidate_keeps_all_months_and_reports_undefined_sharpe():
    s,c,p=fixture()
    c=Config(**{**c.model_dump(),"min_amount":1e30})
    result=run_walkforward(c,s,p,[{"low_vol_window":20},{"low_vol_window":40}])
    assert len(result.windows)==2
    assert all(w["selection_status"]=="cash_fallback" and w["selected_params"]=={"exposure":0.} for w in result.windows)
    assert result.fills.empty
    assert (result.equity.equity==c.capital).all()
    assert result.metrics["sharpe"] is None
    assert result.metrics["max_drawdown"]==0
    assert all(w["replay_return"]==0 for w in result.windows)
