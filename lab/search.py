"""Bounded retrospective exploration; every attempted candidate is recorded."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from lab.config import Config
from lab.engine import run_backtest
from lab.research import run_experiment
from lab.store import save_result
from lab.walkforward import candidates_for


def default_candidates(base):
    result=[]
    for strategy in ("threshold","momentum","low_vol","breakout","reversal"):
        c=Config(**{**base.model_dump(),"strategy":strategy})
        result.extend({"strategy":strategy,**params} for params in candidates_for(c))
    return result


def target_search(base,snapshot,candidates=None,progress=None,root="storage",keep=3):
    candidates=candidates if candidates is not None else default_candidates(base)
    if not candidates or len(candidates)>300:
        raise ValueError("Search requires between 1 and 300 declared candidates")
    forbidden={"start","end","capital","mode","commission","minimum_commission","slippage_bps","participation","risk_free"}
    if any(forbidden.intersection(params) for params in candidates):
        raise ValueError("Search candidates must share evaluation dates, accounting and cost assumptions")
    search_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:8]
    path=Path(root)/"searches"/search_id
    path.mkdir(parents=True)
    definition={"id":search_id,"created_at":datetime.now(timezone.utc).isoformat(),"config":base.model_dump(mode="json"),
                "snapshot_id":snapshot.digest(),"candidates":candidates,"label":"Target-Period Optimized",
                "max_drawdown":.25,"sharpe_target":1.5,"selection_rule":"Prefer drawdown-qualified candidates, then higher Sharpe; otherwise prefer lower drawdown."}
    (path/"definition.json").write_text(json.dumps(definition,indent=2),encoding="utf-8")
    cache,records=[],[]
    cache={}
    for index,params in enumerate(candidates):
        c=Config(**{**base.model_dump(),**params})
        if progress: progress(index/len(candidates)*.8,f"Exploring candidate {index+1}/{len(candidates)}")
        try:
            r=run_backtest(c,snapshot,feature_cache=cache)
            rec={"candidate_id":index,"params":params,"metrics":r.metrics,"state":"completed","run_id":None}
        except (ValueError,ArithmeticError) as exc:
            rec={"candidate_id":index,"params":params,"state":"failed","error":str(exc),"run_id":None}
        records.append(rec)
        (path/"trials.json").write_text(json.dumps(records,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    completed=[r for r in records if r["state"]=="completed" and r["metrics"]["sharpe"] is not None]
    if not completed:
        raise ValueError("No candidate produced a defined Sharpe ratio; all attempts were retained in the search log")
    def rank(row):
        m=row["metrics"]
        qualified=abs(m["max_drawdown"])<=.25
        return (qualified,m["sharpe"] if qualified else -abs(m["max_drawdown"]),m["sharpe"],-row["candidate_id"])
    chosen=sorted(completed,key=rank,reverse=True)[:keep]
    paths=[]
    for i,record in enumerate(chosen):
        c=Config(**{**base.model_dump(),**record["params"]})
        callback=(lambda v,msg,i=i:progress(.8+.19*(i+v)/len(chosen),msg)) if progress else None
        result=run_experiment(c,snapshot,callback,feature_cache=cache)
        result.manifest.update(study="Target-period parameter exploration",target_period_optimized=True,
                               search_id=search_id,search_candidate_id=record["candidate_id"],search_attempts=len(records))
        output=save_result(result,root)
        record["run_id"]=output.name
        paths.append(output)
    definition.update(best_run=paths[0].name,completed_at=datetime.now(timezone.utc).isoformat())
    (path/"definition.json").write_text(json.dumps(definition,indent=2),encoding="utf-8")
    (path/"trials.json").write_text(json.dumps(records,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    return paths[0]
