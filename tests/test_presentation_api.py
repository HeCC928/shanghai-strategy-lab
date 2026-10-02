"""Check the app boundary with real engine artifacts in an isolated directory."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/".runtime"/"python"))
import pytest
from fastapi.testclient import TestClient
import api.main as web
from lab.config import Config
from lab.demo import synthetic_snapshot
from lab.research import run_experiment
from lab.store import save_result


@pytest.fixture
def client(tmp_path,monkeypatch):
    s=synthetic_snapshot(2,"2023-01-02","2023-06-30")
    snap=s.save(tmp_path/"snapshots")
    c=Config(strategy="low_vol",start="2023-04-01",end="2023-06-30",min_history=20,min_amount=0,top_n=2,max_weight=.5,low_vol_window=20)
    r=run_experiment(c,s)
    path=save_result(r,tmp_path)
    monkeypatch.setattr(web,"STORAGE",tmp_path)
    web.table.cache_clear()
    yield TestClient(web.app),path.name,snap.name
    web.table.cache_clear()


def test_trade_link_returns_its_own_plan_and_actual_fills(client):
    c,run,snapshot=client
    rows=c.get(f"/api/runs/{run}/trades").json()
    buy=next(x for x in rows["items"] if x["side"]=="buy")
    r=c.get(f"/api/runs/{run}/trades/{buy['order_id']}")
    assert r.status_code==200
    detail=r.json()
    assert detail["trade"]["order_id"]==buy["order_id"]
    assert all(x["plan_id"]==buy["plan_id"] for x in detail["stages"])
    assert detail["bars"] and detail["decision"]
    assert detail["decision"][0]["signal_date"] == detail["plan"][0]["signal_date"]
    assert next(x for x in detail["holdings"] if x["date"]==buy["date"])["quantity"] >= buy["quantity"]-1e-8
    assert any(x["order_id"]==buy["order_id"] for x in detail["symbol_fills"])
    detail_page=c.get(f"/api/runs/{run}").json()
    assert detail_page["metrics"]["fills"]==rows["total"]


def test_missing_dates_do_not_silently_shorten_a_run(client):
    c,run,snapshot=client
    config=c.get(f"/api/runs/{run}").json()["config"]
    config["end"]="2026-06-30"
    response=c.post("/api/jobs",json={"config":config,"snapshot_id":snapshot})
    assert response.status_code==422
    assert "cover" in response.json()["detail"]


def test_local_write_boundary_and_english_report(client):
    c,run,snapshot=client
    assert c.post("/api/jobs",json={},headers={"origin":"https://unrelated.example"}).status_code==403
    assert c.get("/api/runs/not-a-real-run").status_code==404
    report=c.get(f"/api/runs/{run}/report")
    assert report.status_code==200 and 'lang="en"' in report.text
    assert "cdn.plot.ly" not in report.text.split('<script type="text/javascript">')[0]
    assert "Net equity" in report.text


def test_featured_case_is_explicit_and_evidence_is_self_contained(client, tmp_path, monkeypatch):
    import io
    import json
    import zipfile
    c, run, snapshot = client
    featured = tmp_path / "showcase.json"
    featured.write_text(json.dumps({"featured_run_id":run, "rolling_run_id":"different-run"}))
    monkeypatch.setattr(web,"SHOWCASE",featured)
    assert c.get("/api/runs").json()[0]["featured"] is True
    assert c.get(f"/api/runs/{run}").json()["case_label"] == "Featured fixed rule"
    response = c.get(f"/api/runs/{run}/evidence.zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert {"equity.parquet","metrics.json","config.json","report.html","trades.csv"} <= set(archive.namelist())
        assert b'lang="en"' in archive.read("report.html")
    assert "connect-src 'self'" in c.get("/api/health").headers["content-security-policy"]


def test_equity_png_export_is_a_real_image(client):
    import io
    from PIL import Image
    c,run,snapshot=client
    response=c.get(f"/api/runs/{run}/chart.png")
    assert response.status_code==200 and response.headers['content-type']=='image/png'
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size==(1800,1200)
