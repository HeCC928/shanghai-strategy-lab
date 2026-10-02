from pathlib import Path
import time

from streamlit.testing.v1 import AppTest
from lab.demo import synthetic_snapshot


def test_workbench_load_and_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synthetic_snapshot(2).save()
    app = AppTest.from_file(str(Path(__file__).parents[1]/"app.py"), default_timeout=45).run()
    assert not app.exception
    run = next((b for b in app.button if b.label == "运行回测并保存实验"), None)
    assert run is not None
    run.click().run(timeout=45)
    assert not app.exception
    deadline=time.monotonic()+50
    while not app.session_state.filtered_state.get("result_path") and time.monotonic()<deadline:
        time.sleep(.25)
        app.run(timeout=45)
        assert not app.exception
    assert app.session_state["result_path"]
    next(n for n in app.number_input if n.label=="相邻批次至少间隔（交易日）").set_value(7).run()
    assert any("参数已修改" in x.value for x in app.warning)
    app.sidebar.radio[0].set_value("回测结果").run()
    assert not app.exception
    app.sidebar.radio[0].set_value("交易复盘").run()
    assert not app.exception
    app.sidebar.radio[0].set_value("策略对比").run()
    assert not app.exception
    app.sidebar.radio[0].set_value("数据与实验").run()
    assert not app.exception
    app.sidebar.radio[0].set_value("研究工作台").run()
    assert next(n for n in app.number_input if n.label=="相邻批次至少间隔（交易日）").value==7
