import numpy as np
import pandas as pd
import pytest

from lab.config import Config
from lab.data import Snapshot
from lab.demo import synthetic_snapshot
from lab.engine import run_backtest
from lab.fees import costs
from lab.strategies import compute_features


def controlled(prices, opens=None):
    dates = pd.bdate_range("2023-01-02", periods=len(prices)).strftime("%Y-%m-%d").tolist()
    opening = prices if opens is None else opens
    f = pd.DataFrame({"symbol": "600000", "date": dates, "amount": 1e8, "volume": 1e7,
                      "is_st": False, "is_suspended": False})
    for prefix in ("raw", "adj"):
        f[f"{prefix}_open"] = opening
        f[f"{prefix}_close"] = prices
        f[f"{prefix}_high"] = np.maximum(prices, opening)
        f[f"{prefix}_low"] = np.minimum(prices, opening)
    ins = pd.DataFrame([{"symbol": "600000", "name": "手工样本", "exchange": "SSE", "board": "MAIN_A", "list_date": dates[0]}])
    return Snapshot(f, ins, dates, {"source": "synthetic"})


def config(s, **changes):
    return Config(start=s.calendar[20], end=s.calendar[-1], capital=10000, min_history=20,
                  min_amount=0, threshold_ma=20, top_n=1, max_weight=1,
                  daily_buy_cap=1, participation=1, commission=0, slippage_bps=0, **changes)


def test_independent_hand_ledger_and_signal_delay():
    # First 20 closes 10; day 20 close 11 crosses threshold. Execution at 12 next day.
    # 10000 / 12 shares; next close 13 -> NAV 10833 1/3. No fee, no same-close fill.
    s = controlled([10.]*20+[11., 13., 13., 13.], [10.]*20+[10., 12., 13., 13.])
    r = run_backtest(config(s, staging=False), s)
    assert r.fills.iloc[0].date == s.calendar[21]
    assert r.fills.iloc[0].signal_date == s.calendar[20]
    assert r.fills.iloc[0].quantity == pytest.approx(10000/12)
    assert r.equity.iloc[2].equity == pytest.approx(10000/12*13)
    assert r.equity.cash.min() >= 0


def test_three_tranches_and_no_duplicate_cross():
    s = controlled([10.]*20+list(np.linspace(11, 15, 20)))
    r = run_backtest(config(s, staging=True, tranche_gap=2), s)
    buys = r.fills[r.fills.side == "buy"]
    assert buys.stage.tolist() == [1, 2, 3]
    assert buys.amount.tolist() == pytest.approx([4000, 3000, 3000])
    assert len(r.plans) == 1
    indices = [s.calendar.index(d) for d in buys.date]
    assert indices == [21, 24, 27]


def test_future_mutation_does_not_change_past():
    s = synthetic_snapshot(2, end="2018-08-01")
    c = Config(start="2018-01-01", end="2018-07-31")
    before = run_backtest(c, s)
    mutated = Snapshot(s.bars.copy(), s.instruments, s.calendar, s.manifest)
    cols = [col for col in s.bars if col.startswith(("raw_", "adj_"))]
    mutated.bars.loc[mutated.bars.date > "2018-05-01", cols] *= 2
    after = run_backtest(c, mutated)
    # Orders' realized fills after the cutoff may legitimately change. Compare
    # only the order intent actually available at the signal close.
    fields=["symbol","side","signal_date","quantity","budget","reason","plan_id","stage"]
    pd.testing.assert_frame_equal(before.orders.loc[before.orders.signal_date <= "2018-05-01",fields].reset_index(drop=True),
                                  after.orders.loc[after.orders.signal_date <= "2018-05-01",fields].reset_index(drop=True))
    fa,fb=compute_features(s,c),compute_features(mutated,c)
    pd.testing.assert_frame_equal(fa[fa.date<="2018-05-01"].reset_index(drop=True),fb[fb.date<="2018-05-01"].reset_index(drop=True))


def test_historical_stamp_tax_boundary():
    c = Config()
    assert costs(10000, "sell", "2023-08-25", c)["stamp_tax"] == 10
    assert costs(10000, "sell", "2023-08-28", c)["stamp_tax"] == 5
    assert costs(10000, "buy", "2023-08-28", c)["stamp_tax"] == 0


def test_suspension_retries_then_plan_cancel():
    s = controlled([10.]*20+list(np.linspace(11, 15, 10)))
    s.bars.loc[21:23, "is_suspended"] = True
    r = run_backtest(config(s), s)
    assert r.fills.empty
    assert len(r.orders) == 3
    assert (r.orders.reject_reason == "停牌").all()
    assert r.plans.iloc[0].status == "超过尝试次数"


def test_gap_and_bad_ohlc_rejected():
    s = controlled([10.]*30)
    s.bars = s.bars.drop(index=25)
    with pytest.raises(ValueError, match="缺口"):
        s.validate()
    s = controlled([10.]*30)
    s.bars.loc[2, "raw_high"] = 9
    with pytest.raises(ValueError, match="OHLC"):
        s.validate()


def test_no_trade_metrics_are_not_fabricated():
    s = controlled([10.]*30)
    r = run_backtest(config(s), s)
    assert r.metrics["total_return"] == 0
    assert r.metrics["sharpe"] is None
    assert r.metrics["win_rate"] is None


@pytest.mark.parametrize("strategy", ["momentum", "low_vol", "breakout", "reversal"])
def test_shared_engine_reproducible(strategy):
    s = synthetic_snapshot(2, end="2018-04-10")
    c = Config(strategy=strategy, start="2018-01-01", end="2018-03-30")
    a, b = run_backtest(c, s), run_backtest(c, s)
    pd.testing.assert_frame_equal(a.equity, b.equity)
    assert np.isfinite(a.equity.equity).all()


def test_snapshot_roundtrip_and_tamper(tmp_path):
    s = controlled([10.]*30)
    path = s.save(tmp_path)
    loaded = Snapshot.load(path)
    assert loaded.digest() == s.digest()
    altered = pd.read_parquet(path / "bars.parquet")
    altered.loc[0, "amount"] = 2e8
    altered.to_parquet(path / "bars.parquet")
    with pytest.raises(ValueError, match="校验失败"):
        Snapshot.load(path)


def test_two_stock_ten_day_independent_ledger():
    s=controlled([10.]*29+[12.])
    b=s.bars.copy()
    b["symbol"]="600004"
    for col in [x for x in b if x.startswith(("raw_","adj_"))]:
        b[col]=[20.]*29+[22.]
    s.bars=pd.concat([s.bars,b],ignore_index=True)
    ins=s.instruments.copy()
    ins["symbol"]="600004"
    s.instruments=pd.concat([s.instruments,ins],ignore_index=True)
    c=Config(**{**config(s,staging=False).model_dump(),"strategy":"buy_hold","top_n":2})
    r=run_backtest(c,s)
    # Beginning: 500 shares at 10, 250 shares at 20. Final: 500*12 + 250*22.
    assert r.fills.quantity.tolist()==pytest.approx([500,250])
    assert len(r.equity)==11  # initial capital row + ten trading days
    assert r.equity.equity.iloc[-1]==pytest.approx(11500)


def test_slippage_is_in_price_not_charged_twice():
    s=controlled([10.]*20+[11.]*10)
    c=Config(**{**config(s,staging=False).model_dump(),"slippage_bps":100})
    r=run_backtest(c,s)
    assert r.fills.iloc[0].price==pytest.approx(11.11)
    assert r.equity.equity.iloc[-1]==pytest.approx(10000/1.01)
    assert r.metrics["unrealized_pnl"]==pytest.approx(10000/1.01-10000)


def test_known_limit_rejects_buy_and_does_not_create_position():
    s=controlled([10.]*20+[11.]*10)
    s.bars["limit_up"]=11.
    r=run_backtest(config(s),s)
    assert r.fills.empty
    assert set(r.orders.reject_reason)=={"开盘涨停"}
    assert r.equity.equity.iloc[-1]==10000
