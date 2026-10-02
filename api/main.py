"""Local API and bundled frontend. Only explicit job submission performs work."""
from functools import lru_cache
import html
import io
import json
import os
from pathlib import Path
import re
from typing import Literal
from urllib.parse import urlparse
import zipfile

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict
import pandas as pd
import plotly.graph_objects as go

from api.presentation import NAMES, english, limitations, read_json, records, summary
from lab.config import Config
from lab.data import Snapshot
from lab.strategies import compute_features
from lab.protocols import WalkForwardConfig
from lab.jobs import cancel_job, read_job, running_jobs, start_job
from lab.metrics import monthly_returns

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
SHOWCASE = ROOT / "configs" / "showcase.json"
app = FastAPI(title="Shanghai Strategy Lab", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.exception_handler(RequestValidationError)
async def invalid_configuration(request, exc):
    fields = [".".join(str(x) for x in item["loc"][1:]) or "configuration" for item in exc.errors()]
    return JSONResponse({"detail": "Invalid " + ", ".join(dict.fromkeys(fields)) + ". Check date order, moving-average windows, entry/exit thresholds and allocation limits."}, status_code=422)


@app.middleware("http")
async def same_origin_write(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Please submit requests from the local app."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Local assets and data only, including when the computer remains connected.
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:"
    return response


def resource(kind, key):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key):
        raise HTTPException(404, "Resource not found")
    path = STORAGE / kind / key
    if not path.is_dir():
        raise HTTPException(404, "Resource not found")
    return path


@lru_cache(maxsize=24)
def table(run_id, name):
    return pd.read_parquet(resource("runs", run_id) / f"{name}.parquet")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "shanghai-strategy-lab", "version": "0.2.0", "offline": os.environ.get("LAB_OFFLINE") == "1"}


@app.get("/api/runs")
def runs():
    result = []
    for path in sorted((STORAGE / "runs").glob("*/config.json"), reverse=True):
        if (path.parent / "metrics.json").exists() and (path.parent / "manifest.json").exists():
            result.append(present_run(path.parent))
    return result


def present_run(path):
    out = summary(path)
    featured = read_json(SHOWCASE) if SHOWCASE.exists() else {}
    out["featured"] = path.name == featured.get("featured_run_id")
    out["rolling_comparison"] = path.name == featured.get("rolling_run_id")
    out["case_label"] = "Featured fixed rule" if out["featured"] else "Monthly rolling rule" if out["rolling_comparison"] else out["name"]
    for comparison in featured.get("comparisons", {}).values():
        if comparison["run_id"] == path.name:
            out["case_label"] = comparison["label"]
    return out


@app.get("/api/showcase")
def showcase():
    return read_json(SHOWCASE) if SHOWCASE.exists() else {}


@app.get("/api/snapshots")
def snapshots():
    rows = []
    for p in (STORAGE / "snapshots").glob("*/manifest.json"):
        m = read_json(p)
        cal = read_json(p.parent / "calendar.json")
        ins = pd.read_parquet(p.parent / "instruments.parquet", columns=["symbol"])
        rows.append({"id": p.parent.name, "source": m.get("source", "unknown"),
                     "start": m.get("start", cal[0]), "end": m.get("end", cal[-1]),
                     "first_session": cal[0], "last_session": cal[-1], "stocks": len(ins),
                     "target_ready": cal[0] <= "2023-01-03" and cal[-1] >= "2026-06-30"})
    return sorted(rows, key=lambda x: (x["end"], x["stocks"]), reverse=True)


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str):
    p = resource("runs", run_id)
    out = present_run(p)
    e = table(run_id, "equity").copy()
    e["nav"] = e.equity / out["config"]["capital"]
    e["drawdown"] = e.equity / e.equity.cummax() - 1
    e["exposure"] = 1 - e.cash / e.equity
    out["equity"] = records(e)
    out["benchmarks"] = records(table(run_id, "benchmarks"))
    out["monthly"] = records(monthly_returns(e))
    out["limitations"] = limitations(out["config"], read_json(p / "manifest.json"))
    out["benchmark_metrics"] = read_json(p / "benchmark_metrics.json")
    manifest = read_json(p/"manifest.json")
    out["windows"] = read_json(p / "windows.json") if (p / "windows.json").exists() else []
    out["search_trials"] = []
    if manifest.get("search_id"):
        search = resource("searches",manifest["search_id"])
        out["search_trials"] = read_json(search/"trials.json")
    out["search_attempts"] = manifest.get("search_attempts",0)
    out["risk_states"] = records(table(run_id,"risk_states")) if (p/"risk_states.parquet").exists() else []
    out["selection_trials"] = records(table(run_id,"selection_trials")) if (p/"selection_trials.parquet").exists() else []
    return out


@app.get("/api/runs/{run_id}/trades")
def trades(run_id: str, month: str = "", symbol: str = "", offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    f = table(run_id, "fills")
    if month:
        f = f[f.date.str.startswith(month)]
    if symbol:
        f = f[f.symbol == symbol]
    f = f.sort_values(["date", "order_id"], ascending=[False, False]) if not f.empty else f
    return {"total": len(f), "items": records(f.iloc[offset:offset + limit])}


@app.get("/api/runs/{run_id}/trades/{order_id}")
def trade_detail(run_id: str, order_id: str):
    p = resource("runs", run_id)
    f = table(run_id, "fills")
    found = f[f.order_id == order_id] if "order_id" in f else f.iloc[:0]
    if found.empty:
        raise HTTPException(404, "Trade not found")
    item = found.iloc[0]
    symbol, plan_id = item.symbol, item.get("plan_id", "")
    plans = table(run_id, "plans")
    plan = plans[plans.plan_id == plan_id] if plan_id and "plan_id" in plans else plans.iloc[:0]
    siblings = f[f.plan_id == plan_id] if plan_id else found
    orders = table(run_id, "orders")
    attempts = orders[orders.plan_id == plan_id] if plan_id and "plan_id" in orders else orders[orders.order_id == order_id]
    allocation_date = plan.iloc[0].signal_date if not plan.empty else item.signal_date
    decisions = pd.read_parquet(p / "decisions.parquet", filters=[("symbol", "==", symbol), ("signal_date", "<=", allocation_date)])
    decision = decisions.sort_values("signal_date").tail(1)
    snapshot_id = read_json(p / "manifest.json")["snapshot_id"][:16]
    snap = resource("snapshots", snapshot_id)
    start = (pd.Timestamp(item.date) - pd.Timedelta(days=100)).strftime("%Y-%m-%d")
    end = (pd.Timestamp(item.date) + pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    bars = pd.read_parquet(snap / "bars.parquet", filters=[("symbol", "==", symbol), ("date", ">=", start), ("date", "<=", end)])
    config = read_json(p / "config.json")
    active_config = dict(config)
    for entry in read_json(p/"manifest.json").get("parameter_schedule",[]):
        if entry["signal_date"] <= item.signal_date:
            active_config = {**config, **entry["params"]}
    history = pd.read_parquet(snap/"bars.parquet",filters=[("symbol","==",symbol),("date","<=",item.signal_date)])
    instruments = pd.read_parquet(snap/"instruments.parquet",filters=[("symbol","==",symbol)])
    calendar = [day for day in read_json(snap/"calendar.json") if day<=item.signal_date]
    features = compute_features(Snapshot(history,instruments,calendar),Config(**active_config))
    signal = features[features.date==item.signal_date][["date","deviation","momentum","volatility","qualified","reason"]]
    positions = table(run_id, "positions")
    positions = positions[(positions.symbol == symbol) & (positions.date >= start) & (positions.date <= end)]
    days = table(run_id, "equity")[["date"]]
    days = days[(days.date >= start) & (days.date <= end)]
    holdings = days.merge(positions[["date", "quantity", "value", "weight"]], on="date", how="left").fillna(0)
    symbol_fills = f[(f.symbol == symbol) & (f.date >= start) & (f.date <= end)]
    return {"trade": records(found)[0], "plan": records(plan), "stages": records(siblings),
            "attempts": records(attempts), "decision": records(decision), "bars": records(bars),
            "signal": records(signal), "config": active_config, "holdings": records(holdings), "symbol_fills": records(symbol_fills)}


@app.get("/api/runs/{run_id}/report")
def report(run_id: str):
    r = run_detail(run_id)
    fig = go.Figure()
    fig.add_scatter(x=[e["date"] for e in r["equity"]], y=[e["nav"] for e in r["equity"]], name=r["name"])
    for key, name in [("buy_hold", "Same-pool buy & hold"), ("equal_weight", "Equal-weight rebalance")]:
        if r["benchmarks"] and key in r["benchmarks"][0]:
            fig.add_scatter(x=[e["date"] for e in r["benchmarks"]], y=[e[key] / r["config"]["capital"] for e in r["benchmarks"]], name=name)
    fig.update_layout(template="plotly_white", title="Net equity · initial value = 1", yaxis_title="Net asset value")
    warnings = "".join(f"<li>{html.escape(x)}</li>" for x in r["limitations"])
    m = r["metrics"]
    def formatted(key, kind="number"):
        value = m.get(key)
        if value is None:
            return "Not defined"
        if kind == "percent":
            return f"{value*100:.2f}%"
        if kind == "loss":
            return f"{abs(value)*100:.2f}%"
        if kind == "currency":
            return f"¥{value:,.2f}"
        if kind == "integer":
            return f"{value:,}"
        return f"{value:.2f}"
    metric_table = pd.DataFrame([(label, formatted(key, kind)) for key,label,kind in [
        ("total_return","Net return","percent"),("cagr","Annualized return","percent"),
        ("sharpe","Annualized Sharpe","number"),("max_drawdown","Maximum drawdown loss","loss"),
        ("volatility","Annualized volatility","percent"),("fees","Explicit trading fees","currency"),
        ("slippage_loss","Slippage included in execution prices","currency"),("fills","Filled orders","integer"),
        ("win_rate","Winning matched lots","percent"),("turnover","Annualized one-way turnover (times)","number"),
        ("average_cash_weight","Average cash allocation","percent"),("final_cash_weight","Final cash allocation","percent"),
        ("final_largest_weight","Largest final stock weight","percent")]], columns=["Metric","Value"])
    cards = "".join(f"<div class='card'><small>{label}</small><strong>{formatted(key,kind)}</strong></div>" for key,label,kind in [("total_return","NET RETURN","percent"),("sharpe","SHARPE RATIO","number"),("max_drawdown","MAXIMUM DRAWDOWN","loss")])
    evidence = ""
    if r["featured"]:
        evidence += f"<h2>Featured case</h2><p>Sharpe {r['metrics']['sharpe']:.2f}; maximum drawdown {abs(r['metrics']['max_drawdown'])*100:.1f}%. Target-period optimized result. Not an independent holdout test.</p>"
    if r["windows"]:
        columns = ["month", "signal_date", "candidate_id", "replay_return", "replay_drawdown", "selected_params"]
        evidence += "<h2>Recorded rolling windows</h2><p>12-month calibration, 3-month validation, 1-month replay. Cash and holdings carry across months.</p>" + pd.DataFrame(r["windows"])[columns].to_html(index=False, escape=True)
        evidence += "<details><summary>Full window selection evidence</summary><pre>" + html.escape(json.dumps(r["windows"], indent=2)) + "</pre></details>"
    if r["search_trials"]:
        evidence += f"<h2>Target-period exploration</h2><p>{len(r['search_trials'])} recorded attempts. The displayed case was selected after inspecting this period.</p><details><summary>All attempts</summary><pre>" + html.escape(json.dumps(r["search_trials"], indent=2)) + "</pre></details>"
    body = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Shanghai Strategy Lab · Research report</title>
    <style>body{{font:15px system-ui;color:#19233c;max-width:1100px;margin:40px auto;padding:24px;line-height:1.6}}h1{{font-size:32px;letter-spacing:-1px}}h2{{margin-top:32px}}.eyebrow{{color:#7162c9;letter-spacing:2px;font-size:12px}}.cards{{display:flex;gap:16px;margin:28px 0}}.card{{flex:1;background:#f3f1fc;border-radius:12px;padding:20px}}.card small{{display:block;color:#6c6982;font-size:11px}}.card strong{{display:block;font-size:30px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #dde2ec;text-align:left}}th{{background:#f6f7fb}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f7fb;padding:16px}}details{{margin:16px 0}}li{{margin:6px 0}}@media(max-width:650px){{.cards{{flex-direction:column}}}}</style>
    <div class="eyebrow">SHANGHAI STRATEGY LAB · FINTECH RESEARCH</div><h1>{html.escape(r['case_label'])}</h1><p>Research report · {r['config']['start']} — {r['config']['end']} · {html.escape(r['study'])}</p><div class="cards">{cards}</div>
    <ul>{warnings}</ul>{fig.to_html(full_html=False, include_plotlyjs=True)}<h2>Metrics</h2>{metric_table.to_html(index=False, escape=True)}
    {evidence}<details><summary>Full precision metrics</summary><pre>{html.escape(json.dumps(m, indent=2))}</pre></details><h2>Configuration</h2><pre>{html.escape(json.dumps(r['config'], indent=2))}</pre><h2>Provenance</h2><p>Run: {run_id}<br>Snapshot: {r['snapshot_id']}<br>Source: {html.escape(r['source'])}</p></html>'''
    return HTMLResponse(body, headers={"Content-Disposition": f'attachment; filename="{run_id}-report.html"'})


@app.get("/api/runs/{run_id}/report/preview")
def report_preview(run_id: str):
    return HTMLResponse(report(run_id).body)


@app.get("/api/runs/{run_id}/trades.csv")
def trades_csv(run_id: str):
    f = pd.DataFrame(records(table(run_id, "fills")))
    return Response(f.to_csv(index=False).encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{run_id}-trades.csv"'})


@app.get("/api/runs/{run_id}/chart.png")
def chart_png(run_id: str):
    from api.figures import equity_png
    return Response(equity_png(run_detail(run_id)), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{run_id}-equity.png"'})


@app.get("/api/runs/{run_id}/evidence.zip")
def evidence_zip(run_id: str):
    path = resource("runs", run_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in path.iterdir():
            if file.suffix in (".json", ".parquet"):
                archive.write(file, file.name)
        archive.writestr("report.html", report(run_id).body)
        archive.writestr("trades.csv", trades_csv(run_id).body)
        manifest = read_json(path / "manifest.json")
        if manifest.get("search_id"):
            for file in resource("searches", manifest["search_id"]).glob("*.json"):
                archive.write(file, "search/" + file.name)
    return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{run_id}-evidence.zip"'})


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: str
    config: Config
    kind: Literal["run", "walkforward", "search"] = "run"
    protocol: WalkForwardConfig | None = None


@app.post("/api/jobs", status_code=202)
def submit(body: RunRequest):
    snapshot = resource("snapshots", body.snapshot_id)
    manifest = read_json(snapshot / "manifest.json")
    cal = read_json(snapshot / "calendar.json")
    if str(body.config.start) < manifest.get("start", cal[0]) or str(body.config.end) > manifest.get("end", cal[-1]):
        raise HTTPException(422, "Selected data does not cover the requested dates. Choose a complete snapshot or adjust the dates.")
    payload = {"config": body.config.model_dump(mode="json"), "snapshot": str(snapshot), "output_root": str(STORAGE),
               "target_period_optimized": str(body.config.start)=="2025-07-01" and str(body.config.end)=="2026-06-30"}
    if body.kind == "walkforward":
        try:
            protocol = body.protocol or WalkForwardConfig(start=body.config.start,end=body.config.end)
        except ValueError:
            raise HTTPException(422,"Rolling research requires complete calendar months.")
        payload["protocol"] = protocol.model_dump(mode="json")
        if protocol.start != body.config.start or protocol.end != body.config.end:
            raise HTTPException(422,"Protocol and experiment dates must match.")
        if body.config.strategy not in NAMES or body.config.strategy in ("buy_hold","equal_weight"):
            raise HTTPException(422,"Choose one of the five research strategies for rolling selection.")
    try:
        path = start_job(body.kind, payload)
    except RuntimeError:
        raise HTTPException(409, "A calculation is already running. Wait or cancel it before starting another.")
    return {"id": Path(path).name}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    state = read_job(resource("jobs", job_id))
    output = Path(state["output"]).name if state.get("output") else None
    messages = {"queued": "Preparing the experiment", "running": "Calculating with the saved data", "completed": "Experiment saved", "cancelled": "Calculation cancelled", "cancelling": "Cancelling safely", "failed": "Calculation failed. Inspect the local job log for details.", "interrupted": "The worker stopped before saving a complete experiment."}
    return {"id": job_id, "state": state["state"], "progress": state.get("progress", 0), "message": messages.get(state["state"], "Working"), "output": output}


@app.get("/api/jobs")
def active_jobs():
    return [job(Path(s["path"]).name) for s in running_jobs(STORAGE / "jobs") if s["state"] in ("queued", "running", "cancelling")]


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: str):
    path = resource("jobs", job_id)
    state = read_job(path)
    if state["state"] not in ("queued", "running", "cancelling"):
        raise HTTPException(409, "This calculation has already stopped.")
    cancel_job(path)
    return {"state": "cancelling"}


dist = ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
