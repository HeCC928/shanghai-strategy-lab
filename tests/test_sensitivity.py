from lab.config import Config
from lab.demo import synthetic_snapshot
from lab.sensitivity import run_sensitivity


def test_grid_respects_the_declared_evaluation_period():
    s=synthetic_snapshot(1,start="2021-01-01",end="2023-02-01")
    r=run_sensitivity(Config(start="2023-01-01",end="2023-02-01"),s)
    assert len(r)==9
    assert set(r.threshold_ma)=={10,20,30}
    assert set(r.evaluation_start)=={"2023-01-01"}
    assert set(r.evaluation_end)=={"2023-02-01"}
    assert all(r.drawdown_peak >= "2022-12-30")
