"""Independently verify saved evidence and freeze its file hashes."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'.runtime/python'))
from api.main import report, trades_csv, chart_png

def main():
    showcase=json.loads((ROOT/'configs/showcase.json').read_text())
    cases={'featured':showcase['featured_run_id'],'rolling':showcase['rolling_run_id']}
    cases.update({k:v['run_id'] for k,v in showcase['comparisons'].items()})
    checks={}
    files={}
    destination=ROOT/'storage/showcase'
    destination.mkdir(exist_ok=True)
    for role,identifier in cases.items():
        path=ROOT/'storage/runs'/identifier
        equity=pd.read_parquet(path/'equity.parquet')
        metrics=json.loads((path/'metrics.json').read_text())
        config=json.loads((path/'config.json').read_text())
        assert config['start']=='2025-07-01' and config['end']=='2026-06-30'
        assert equity.date.is_unique and equity.date.is_monotonic_increasing
        assert equity.initial.sum()==1 and equity.iloc[0].equity==config['capital']
        returns=equity.equity.pct_change(fill_method=None).dropna()-((1+config['risk_free'])**(1/252)-1)
        calculated={'sharpe':float(np.sqrt(252)*returns.mean()/returns.std(ddof=1)),
                    'max_drawdown':float((equity.equity/equity.equity.cummax()-1).min()),
                    'total_return':float(equity.equity.iloc[-1]/equity.equity.iloc[0]-1)}
        for key,value in calculated.items():
            assert abs(value-metrics[key])<1e-10,(role,key,value,metrics[key])
        checks[role]={'id':identifier,**calculated,'sessions':len(returns)}
        if role=='featured':
            assert round(calculated['sharpe'],2)==1.48
            assert round(abs(calculated['max_drawdown'])*100,1)==19.3
            assert abs(calculated['max_drawdown'])<=.25
        (destination/f'{role}-report.html').write_bytes(report(identifier).body)
        (destination/f'{role}-trades.csv').write_bytes(trades_csv(identifier).body)
        (destination/f'{role}-equity.png').write_bytes(chart_png(identifier).body)
        for file in path.iterdir():
            if file.suffix in ('.json','.parquet'):
                files[file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
    rolling=ROOT/'storage/runs'/showcase['rolling_run_id']
    windows=json.loads((rolling/'windows.json').read_text())
    assert len(windows)==12
    assert [w['month'] for w in windows]==[str(x) for x in pd.period_range('2025-07','2026-06',freq='M')]
    for w in windows:
        # Calendar month-end may be a weekend after the last known trading close.
        assert w['train_end']<w['validation_start']<=w['signal_date']<=w['validation_end']<w['first_session']
    trials=pd.read_parquet(rolling/'selection_trials.parquet')
    assert len(trials)==168 and set(trials.month)==set(w['month'] for w in windows)
    search=ROOT/'storage/searches'/showcase['search_id']
    attempts=json.loads((search/'trials.json').read_text())
    assert len(attempts)==45
    snapshot=ROOT/'storage/snapshots'/showcase['snapshot_id']
    bars=pd.read_parquet(snapshot/'bars.parquet')
    assert bars.symbol.nunique()==100 and len(bars)==84300
    coverage=bars.groupby('symbol').agg(first=('date','min'),last=('date','max'),rows=('date','size'))
    assert (coverage['first']=='2023-01-03').all() and (coverage['last']=='2026-06-30').all() and (coverage.rows==843).all()
    for file in [*snapshot.iterdir(),*search.glob('*.json')]:
        if file.is_file():files[file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
    payload={'verified_at':datetime.now(timezone.utc).isoformat(),'cases':checks,'search_configurations':45,
             'rolling_candidates':9,'rolling_calibration_trials':108,'rolling_validation_trials':60,
             'declared_comparisons':4,'snapshot_rows':84300,'hashes':files,
             'scope':'Saved numerical artifacts and exports. Browser and offline checks are documented separately.'}
    (destination/'verification.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k!='hashes'},indent=2))

if __name__=='__main__': main()
