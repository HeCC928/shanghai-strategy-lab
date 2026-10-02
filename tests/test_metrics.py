import pandas as pd
import pytest
from lab.metrics import period_metrics


def test_range_return_includes_first_selected_day_and_does_not_mutate_full_equity():
    equity=pd.DataFrame({"date":["2023-01-02","2023-01-03","2023-01-04","2023-01-05"],"equity":[100.,110.,99.,108.9],"initial":[True,False,False,False]})
    result=period_metrics(equity,"2023-01-04","2023-01-05")
    assert result["区间收益"]==pytest.approx(-.01)
    assert result["最大回撤损失"]==pytest.approx(.1)
    assert equity.equity.tolist()==[100.,110.,99.,108.9]
