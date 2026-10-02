"""Verify saved artifacts and measure local load/chart/export costs."""
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import zipfile
import io

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import psutil
from lab.data import Snapshot
from lab.store import load_result,export_zip
from lab.charts import equity_chart
from lab.shares import strict_data_issues

catalog=pd.read_csv("docs/evidence/computed_reports.csv")
checks=[]
for row in catalog.itertuples():
    t=perf_counter();r=load_result(row.run_path);load_seconds=perf_counter()-t
    t=perf_counter();fig=equity_chart(r);fig.to_json();chart_seconds=perf_counter()-t
    t=perf_counter();blob=export_zip(r);export_seconds=perf_counter()-t
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        assert z.testzip() is None
        assert {"config.yaml","metrics.json","data_manifest.json","report.html","equity.csv","trades.csv"}.issubset(z.namelist())
    assert len(r.equity)>1700 and r.equity.cash.min()>=-1e-6
    assert abs(r.equity.equity.iloc[-1]/r.equity.equity.iloc[0]-1-r.metrics["total_return"])<1e-10
    positions=r.positions.groupby("date").value.sum().reindex(r.equity.date,fill_value=0).to_numpy()
    assert abs(r.equity.equity-r.equity.cash-r.equity.receivable-positions).max()<1e-5
    checks.append({"strategy":row.strategy,"run_path":row.run_path,"load_seconds":load_seconds,"chart_json_seconds":chart_seconds,"export_seconds":export_seconds,"zip_bytes":len(blob),"asset_equation":"passed",**r.timings})
s=Snapshot.load(Path("storage/snapshots")/r.manifest["snapshot_id"][:16])
report={"environment":{"python":sys.version,"platform":platform.platform(),"logical_cpus":psutil.cpu_count(),"physical_cpus":psutil.cpu_count(logical=False),"ram_gib":round(psutil.virtual_memory().total/2**30,1)},"snapshot":s.digest(),"stocks":len(s.instruments),"bar_rows":len(s.bars),"strict_mode_missing":strict_data_issues(s,r.config),"checks":checks}
Path("docs/evidence/delivery_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
