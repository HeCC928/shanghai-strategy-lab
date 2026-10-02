import io
import zipfile

import pandas as pd

from lab.config import Config
from lab.demo import synthetic_snapshot
from lab.research import run_experiment
from lab.store import export_zip, save_result, load_result


def test_comparators_and_export_roundtrip(tmp_path):
    s=synthetic_snapshot(2,end="2018-04-10")
    c=Config(start="2018-01-01",end="2018-03-30",strategy="low_vol")
    r=run_experiment(c,s)
    assert list(r.benchmarks.date)==list(r.equity.date)
    assert r.benchmarks.buy_hold.iloc[0]==c.capital
    assert r.metrics["annual_excess"]==r.metrics["cagr"]-r.benchmark_metrics["buy_hold"]["cagr"]
    path=save_result(r,tmp_path)
    restored=load_result(path)
    pd.testing.assert_frame_equal(r.equity,restored.equity)
    pd.testing.assert_frame_equal(r.benchmarks,restored.benchmarks)
    with zipfile.ZipFile(io.BytesIO(export_zip(restored))) as archive:
        assert {"config.yaml","metrics.json","equity.csv","trades.csv","holdings.csv","decisions.csv","report.html","data_manifest.json"}.issubset(archive.namelist())
        assert "synthetic" in archive.read("data_manifest.json").decode()
