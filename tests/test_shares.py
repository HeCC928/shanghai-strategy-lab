import pandas as pd
import pytest

from lab.config import Config
from lab.engine import run_backtest
from lab.fees import costs
from lab.shares import ShareBook, sell_lot_size
from test_core import controlled, config


def strict_sample():
    s=controlled([10.]*20+[11.,11.,11.,11.,11.,11.,11.,11.,11.,11.])
    s.bars["no_price_limit"]=False
    s.bars["limit_up"]=20.
    s.bars["limit_down"]=5.
    s.manifest["corporate_action_coverage"]={"600000":{"from":s.calendar[0],"to":s.calendar[-1],"source":"independent_hand_fixture","reviewed_at":"2026-09-13","complete":True}}
    return s


def test_strict_gate_refuses_unverified_data():
    s=controlled([10.]*30)
    with pytest.raises(ValueError,match="验收未通过"):
        run_backtest(config(s).model_copy(update={"mode":"shares"}),s)


def test_real_lots_minimum_fee_and_cash():
    s=strict_sample()
    c=config(s,staging=False).model_copy(update={"mode":"shares","commission":.0003})
    r=run_backtest(c,s)
    buy=r.fills.iloc[0]
    assert buy.quantity==900
    assert buy.commission==5
    assert buy.transfer_fee==pytest.approx(.10)
    assert r.equity.cash.iloc[2]==pytest.approx(10000-9900-5-.10)
    assert (r.fills.loc[r.fills.side=="buy","quantity"]%100==0).all()


def test_t1_and_legal_odd_lot():
    cal=["2023-01-02","2023-01-03","2023-01-04"]
    book=ShareBook(["600000"],cal,pd.DataFrame())
    book.buy("600000",100,10,5,cal[0])
    assert book.available("600000",cal[0])==0
    with pytest.raises(ValueError,match="T\\+1"):
        book.sell("600000",100,10,5,cal[0])
    assert book.available("600000",cal[1])==100
    book.sell("600000",100,11,5,cal[1])
    assert book.quantities["600000"]==0
    assert book.realized[0]["pnl"]==pytest.approx(90)
    assert sell_lot_size(130,250)==50
    assert sell_lot_size(180,250)==150
    assert sell_lot_size(250,250)==250


def test_dividend_and_bonus_do_not_double_count():
    cal=["2023-01-02","2023-01-03","2023-01-04","2023-01-05","2023-01-06"]
    actions=pd.DataFrame([{"event_id":"a1","symbol":"600000","record_date":cal[1],"ex_date":cal[2],"pay_date":cal[4],"cash_per_share":1.,"share_multiplier":2.,"share_trade_date":cal[3],"source":"hand ledger"}])
    book=ShareBook(["600000"],cal,actions)
    book.buy("600000",100,10,0,cal[0])
    book.close_day(cal[1])
    assert book.open_day(cal[2])==0
    assert book.quantities["600000"]==200
    assert book.available("600000",cal[2])==100
    assert book.receivable==100
    # Independent value: (10-1)/2 = 4.5; 200*4.5 + 100 receivable = 1000.
    assert book.quantities["600000"]*4.5+book.receivable==1000
    assert book.open_day(cal[3])==0
    assert book.available("600000",cal[3])==200
    assert book.open_day(cal[4])==100
    assert book.receivable==0
    assert book.open_day(cal[4])==0
    book.sell("600000",200,4.5,0,cal[4])
    assert sum(x["pnl"] for x in book.realized)==pytest.approx(0)


def test_transfer_effective_date():
    c=Config(mode="shares")
    assert costs(10000,"buy","2022-04-28",c)["transfer_fee"]==.2
    assert costs(10000,"buy","2022-04-29",c)["transfer_fee"]==.1


def test_integrated_ex_dividend_cash_and_equity():
    s=strict_sample()
    for col in [x for x in s.bars if x.startswith("raw_")]:
        s.bars.loc[24:,col]=5.
    s.actions=pd.DataFrame([{"event_id":"div1","symbol":"600000","record_date":s.calendar[23],"ex_date":s.calendar[24],"pay_date":s.calendar[26],"cash_per_share":1.,"share_multiplier":2.,"share_trade_date":s.calendar[25],"source":"independent fixture"}])
    c=config(s,staging=False).model_copy(update={"mode":"shares","minimum_commission":0})
    r=run_backtest(c,s)
    e=r.equity.set_index("date")
    assert e.loc[s.calendar[24],"equity"]==pytest.approx(e.loc[s.calendar[23],"equity"])
    assert e.loc[s.calendar[24],"receivable"]==900
    assert e.loc[s.calendar[26],"receivable"]==0
    assert e.loc[s.calendar[26],"cash"]-e.loc[s.calendar[25],"cash"]==900


def test_delisted_asset_does_not_disappear_or_sell_at_last_mark():
    s=strict_sample()
    s.instruments["delist_date"]=s.calendar[24]
    s.bars=s.bars[s.bars.date<=s.calendar[24]].copy()
    c=config(s,staging=False).model_copy(update={"mode":"shares","minimum_commission":0})
    with pytest.raises(ValueError,match="现金回收"):
        run_backtest(c,s)
    s.manifest["exit_records"]=[{"symbol":"600000","recovery_date":s.calendar[27],"net_cash_per_share":3.,"source":"independent cash recovery ledger","known_at":s.calendar[27]}]
    r=run_backtest(c,s)
    e=r.equity.set_index("date")
    assert e.loc[s.calendar[26],"equity"]==pytest.approx(9999.90)
    assert e.loc[s.calendar[27],"equity"]==pytest.approx(99.90+2700)
    assert not (r.fills.side=="sell").any()
