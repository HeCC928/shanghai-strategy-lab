"""Build real computed reports without searching for better parameters."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import yaml
from lab.config import Config,STRATEGIES
from lab.data import Snapshot
from lab.research import run_experiment
from lab.store import save_result

p=argparse.ArgumentParser()
p.add_argument("snapshot")
args=p.parse_args()
s=Snapshot.load(args.snapshot)
rows=[]
for key in STRATEGIES:
    c=Config(strategy=key)
    result=run_experiment(c,s)
    path=save_result(result)
    Path("configs").mkdir(exist_ok=True)
    Path(f"configs/{key}.yaml").write_text(yaml.safe_dump(c.model_dump(mode="json"),allow_unicode=True),encoding="utf-8")
    rows.append({"strategy":key,"run_path":str(path),"source":s.manifest.get("source"),"stocks":len(s.instruments),**result.metrics,**result.timings})
    print(key,path,flush=True)
Path("docs/evidence").mkdir(parents=True,exist_ok=True)
pd.DataFrame(rows).to_csv("docs/evidence/computed_reports.csv",index=False,encoding="utf-8-sig")
s.coverage_report().to_csv("docs/evidence/data_coverage.csv",index=False,encoding="utf-8-sig")
Path("docs/evidence/data_manifest.json").write_text(json.dumps(s.manifest,ensure_ascii=False,indent=2),encoding="utf-8")
