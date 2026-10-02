import json
import pytest
from lab.config import Config
from lab.demo import synthetic_snapshot
from lab.search import target_search


def test_exploration_retains_attempts_and_marks_selected_case(tmp_path):
    s=synthetic_snapshot(2,"2023-01-02","2023-06-30")
    c=Config(strategy="low_vol",start="2023-04-01",end="2023-06-30",min_history=20,min_amount=0,top_n=2,max_weight=.5)
    path=target_search(c,s,[{"low_vol_window":20},{"low_vol_window":40}],root=tmp_path,keep=1)
    manifest=json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["target_period_optimized"] is True
    search=tmp_path/"searches"/manifest["search_id"]
    rows=json.loads((search/"trials.json").read_text(encoding="utf-8"))
    assert len(rows)==2 and all(x["state"]=="completed" for x in rows)
    assert sum(x["run_id"] is not None for x in rows)==1
    assert any(x["run_id"]==path.name for x in rows)


def test_search_cannot_improve_results_by_changing_costs(tmp_path):
    s=synthetic_snapshot(1,"2023-01-02","2023-06-30")
    c=Config(start="2023-04-01",end="2023-06-30")
    with pytest.raises(ValueError,match="cost assumptions"):
        target_search(c,s,[{"commission":0}],root=tmp_path)
