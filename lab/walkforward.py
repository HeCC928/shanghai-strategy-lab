"""Past-only monthly selection followed by a single continuous portfolio replay."""
import itertools
import json
from hashlib import sha256
import math

import pandas as pd

from lab.config import Config
from lab.engine import run_backtest
from lab.metrics import period_metrics
from lab.protocols import WalkForwardConfig
from lab.research import run_experiment
from lab.sensitivity import GRIDS


def candidates_for(config):
    x, xs, y, ys = GRIDS[config.strategy]
    return [{x: a, y: b} for a, b in itertools.product(xs, ys)]


def run_walkforward(config, snapshot, protocol=None, candidates=None, progress=None):
    protocol = protocol or WalkForwardConfig()
    candidates = candidates if candidates is not None else candidates_for(config)
    if not candidates or len(candidates) > 300:
        raise ValueError("Supply between 1 and 300 candidate configurations")
    config = Config(**{**config.model_dump(), "start": protocol.start, "end": protocol.end})
    windows = protocol.windows(snapshot.calendar)
    if snapshot.calendar[0] > windows[0]["train_start"] or snapshot.calendar[-1] < windows[-1]["last_session"]:
        raise ValueError("Snapshot does not cover the calibration and replay history")
    if snapshot.manifest.get("end", snapshot.calendar[-1]) < str(protocol.end):
        raise ValueError("Snapshot ends before the requested complete evaluation period")
    definition = {"protocol": protocol.model_dump(mode="json"), "base_config": config.model_dump(mode="json"), "candidates": candidates}
    definition["protocol_hash"] = sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    cache, rows, schedule, completed = {}, [], [], []
    previous = None
    keys = sorted({key for p in candidates for key in p})
    spans = {key: max(float(p.get(key, getattr(config, key))) for p in candidates) - min(float(p.get(key, getattr(config, key))) for p in candidates) for key in keys}

    def distance(params):
        if previous is None: return 0.
        return sum(abs(float(params.get(k, getattr(config,k))) - float(previous.get(k,getattr(config,k))))/(spans[k] or 1) for k in keys)

    def evaluate(params, window, phase, index):
        start, end = (window["train_start"], window["train_end"]) if phase=="calibration" else (window["validation_start"], window["validation_end"])
        c = Config(**{**config.model_dump(), **params, "start": start, "end": end})
        result = run_backtest(c, snapshot, feature_cache=cache)
        record = {"month": window["month"], "phase": phase, "candidate_id": index, "start": start, "end": end,
                  "params": json.dumps(params, sort_keys=True), "sharpe": result.metrics["sharpe"],
                  "max_drawdown": abs(result.metrics["max_drawdown"]), "turnover": result.metrics["turnover"],
                  "total_return": result.metrics["total_return"], "fills": result.metrics["fills"]}
        rows.append(record)
        if progress: progress((len(completed)+(len([r for r in rows if r['month']==window['month']])/(len(candidates)+min(protocol.shortlist,len(candidates)))))/len(windows)*.8, f"{window['month']} · {phase} · candidate {index+1}")
        return record

    for window in windows:
        training = [evaluate(params,window,"calibration",i) for i,params in enumerate(candidates)]
        valid = [r for r in training if r["sharpe"] is not None and math.isfinite(r["sharpe"])]
        shortlist = sorted(valid,key=lambda r:(-r["sharpe"],r["candidate_id"]))[:protocol.shortlist]
        validation = [evaluate(candidates[r["candidate_id"]],window,"validation",r["candidate_id"]) for r in shortlist]
        eligible = [r for r in validation if r["sharpe"] is not None and math.isfinite(r["sharpe"]) and r["max_drawdown"] <= protocol.max_drawdown and r["turnover"] is not None]
        chosen = None
        if eligible:
            frame = pd.DataFrame(eligible)
            frame["selection_score"] = .5*frame.sharpe.rank(pct=True)+.3*(-frame.max_drawdown).rank(pct=True)+.2*(-frame.turnover).rank(pct=True)
            frame["parameter_distance"] = frame.candidate_id.map(lambda i:distance(candidates[i]))
            ranked = frame.sort_values(["selection_score","parameter_distance","candidate_id"],ascending=[False,True,True])
            chosen = int(ranked.iloc[0].candidate_id)
            for rec in eligible:
                selected_row=frame[frame.candidate_id==rec["candidate_id"]].iloc[0]
                rec["selection_score"]=float(selected_row.selection_score)
                rec["parameter_distance"]=float(selected_row.parameter_distance)
            params = candidates[chosen]
            previous = params
        else:
            params = {"exposure": 0.}
        schedule.append({"signal_date":window["signal_date"],"params":params,"candidate_id":chosen})
        completed.append({**window,"candidate_id":chosen,"selected_params":params,
                          "selection_status":"selected" if chosen is not None else "cash_fallback",
                          "validation_candidates":validation})
    if progress: progress(.8,"Replaying a continuous portfolio ledger")
    callback = (lambda value, text:progress(.8+.19*value,text)) if progress else None
    result = run_experiment(config,snapshot,callback,parameter_schedule=schedule,feature_cache=cache)
    for window in completed:
        metrics = period_metrics(result.equity,window["replay_start"],window["replay_end"],config.risk_free)
        window["replay_return"] = metrics["区间收益"]
        window["replay_drawdown"] = metrics["最大回撤损失"]
    result.windows = completed
    result.selection_trials = pd.DataFrame(rows)
    result.manifest.update(study="Retrospective Walk-Forward", target_period_optimized=protocol.target_period_optimized,
                           walkforward=definition, candidate_configurations=len(candidates), candidate_backtests=len(rows))
    return result
