"""Public synthetic CSV fixture: no downloaded market data is redistributed."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import yaml
from lab.data import Snapshot
from lab.config import Config
from lab.research import run_experiment
from lab.store import save_result

root=Path("examples/strict_synthetic")
root.mkdir(parents=True,exist_ok=True)
dates=pd.bdate_range("2023-01-02",periods=40).strftime("%Y-%m-%d").tolist()
prices=[10.]*20+[11.]*20
b=pd.DataFrame({"symbol":"600000","date":dates,"amount":1e8,"volume":1e7,"is_st":False,"is_suspended":False,"no_price_limit":False,"limit_up":20.,"limit_down":1.})
for prefix in ("raw","adj"):
    for field in ("open","high","low","close"):b[f"{prefix}_{field}"]=prices
for col in [x for x in b if x.startswith("raw_")]:b.loc[30:,col]=5.
ins=pd.DataFrame([{"symbol":"600000","name":"合成记账样本","exchange":"SSE","board":"MAIN_A","list_date":dates[0]}])
actions=pd.DataFrame([{"event_id":"synthetic_dividend","symbol":"600000","record_date":dates[29],"ex_date":dates[30],"pay_date":dates[32],"cash_per_share":1.,"share_multiplier":2.,"share_trade_date":dates[31],"source":"synthetic hand ledger"}])
manifest={"source":"synthetic","label":"合成严格股数CSV样本（非真实行情）","limitations":["所有价格、日历、限制价及事件均为教学合成，不能用于评价策略收益"],"corporate_action_coverage":{"600000":{"from":dates[0],"to":dates[-1],"source":"synthetic hand ledger","reviewed_at":"2026-09-13","complete":True}}}
s=Snapshot(b,ins,dates,manifest,actions)
for name,frame in [("bars",b),("instruments",ins),("calendar",pd.DataFrame({"date":dates})),("actions",actions)]:frame.to_csv(root/f"{name}.csv",index=False,encoding="utf-8-sig")
(root/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
c=Config(mode="shares",start=dates[20],end=dates[-1],capital=10000,min_history=20,min_amount=0,top_n=1,max_weight=1,daily_buy_cap=1,participation=1,slippage_bps=0,staging=False)
(root/"config.yaml").write_text(yaml.safe_dump(c.model_dump(mode="json"),allow_unicode=True),encoding="utf-8")
snapshot=s.save()
result=run_experiment(c,s)
report=save_result(result)
print(snapshot,report)
