"""Immutable result bundles and a lightweight experiment index."""
from datetime import datetime, timezone
from hashlib import sha256
import html
import io
import json
from pathlib import Path
import sqlite3
import uuid
import zipfile

import pandas as pd
import plotly.graph_objects as go
import yaml

from lab.config import Config, STRATEGIES
from lab.engine import Result

TABLES = ["equity", "positions", "decisions", "orders", "fills", "plans", "benchmarks", "corporate_events", "closed_lots", "risk_states", "selection_trials"]


def code_hash():
    paths = sorted(list(Path(__file__).parent.glob("*.py"))+list((Path(__file__).parent/"resources").glob("*.yaml")))
    return sha256(b"".join(p.name.encode()+p.read_bytes() for p in paths)).hexdigest()


def report_html(r: Result):
    f = go.Figure()
    f.add_scatter(x=r.equity.date, y=r.equity.equity/r.config.capital, name="策略净值")
    for key, name in [("buy_hold", "同池买入持有"), ("equal_weight", "同池等权调仓"),("market","上证综指（价格指数）")]:
        if key in r.benchmarks:
            f.add_scatter(x=r.benchmarks.date, y=r.benchmarks[key]/r.config.capital, name=name)
    f.update_layout(template="plotly_white", title="扣费后净值", xaxis_title="日期", yaxis_title="净值（初始=1）")
    config = html.escape(yaml.safe_dump(r.config.model_dump(mode="json"), allow_unicode=True))
    metrics = pd.DataFrame([{k:v for k,v in r.metrics.items()}]).T.to_html(header=False, escape=True)
    limitations = "".join(f"<li>{html.escape(x)}</li>" for x in r.manifest.get("limitations", []))
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>沪A策略研究报告</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;color:#17202a;padding:20px}} table{{border-collapse:collapse}}td,th{{padding:8px;border:1px solid #ddd}}pre{{background:#f7f8fa;padding:20px;white-space:pre-wrap}}</style>
<h1>{html.escape(STRATEGIES.get(r.config.strategy, r.config.strategy))} · 研究报告</h1>
<p>{html.escape(r.manifest.get('label', '数据快照'))} | {r.config.start} 至 {r.config.end} | {r.config.mode}</p>
<ul>{limitations}</ul>{f.to_html(full_html=False, include_plotlyjs=True)}<h2>指标</h2>{metrics}
<h2>实验配置</h2><pre>{config}</pre><h2>数据与代码</h2><pre>{html.escape(json.dumps(r.manifest,ensure_ascii=False,indent=2))}</pre>
<h2>成交记录</h2>{r.fills.to_html(index=False, escape=True)}</html>"""


def export_zip(r: Result):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("config.yaml", yaml.safe_dump(r.config.model_dump(mode="json"), allow_unicode=True))
        z.writestr("metrics.json", json.dumps(r.metrics, ensure_ascii=False, indent=2, allow_nan=False))
        z.writestr("benchmark_metrics.json", json.dumps(r.benchmark_metrics, ensure_ascii=False, indent=2, allow_nan=False))
        z.writestr("data_manifest.json", json.dumps(r.manifest, ensure_ascii=False, indent=2))
        z.writestr("windows.json", json.dumps(r.windows, ensure_ascii=False, indent=2, allow_nan=False))
        names = {"positions": "holdings", "fills": "trades"}
        for table in TABLES:
            z.writestr(names.get(table, table)+".csv", getattr(r, table).to_csv(index=False).encode("utf-8-sig"))
        z.writestr("report.html", report_html(r))
    return buffer.getvalue()


def save_result(r: Result, root="storage"):
    root = Path(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    target = root / "runs" / run_id
    target.mkdir(parents=True)
    r.manifest = {**r.manifest, "run_id": run_id, "code_hash": code_hash(), "created_at": datetime.now(timezone.utc).isoformat()}
    for table in TABLES:
        getattr(r, table).to_parquet(target / f"{table}.parquet", index=False)
    for name, value in [("config", r.config.model_dump(mode="json")), ("manifest", r.manifest), ("metrics", r.metrics), ("timings", r.timings), ("benchmark_metrics", r.benchmark_metrics)]:
        (target / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (target / "report.html").write_text(report_html(r), encoding="utf-8")
    (target / "windows.json").write_text(json.dumps(r.windows, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (target / "export.zip").write_bytes(export_zip(r))
    with sqlite3.connect(root / "experiments.sqlite") as db:
        db.execute("CREATE TABLE IF NOT EXISTS experiments (run_id TEXT PRIMARY KEY, created_at TEXT, strategy TEXT, source TEXT, start TEXT, end TEXT, mode TEXT, snapshot_id TEXT)")
        db.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (run_id, r.manifest["created_at"], r.config.strategy, r.manifest.get("source", "unknown"), str(r.config.start), str(r.config.end), r.config.mode, r.manifest["snapshot_id"]))
    return target


def load_result(path):
    p = Path(path)
    read = lambda name: json.loads((p / f"{name}.json").read_text(encoding="utf-8"))
    tables = {name: pd.read_parquet(p / f"{name}.parquet") if (p / f"{name}.parquet").exists() else pd.DataFrame() for name in TABLES}
    return Result(Config(**read("config")), read("manifest"), **tables, metrics=read("metrics"), timings=read("timings"),
                  windows=read("windows") if (p/"windows.json").exists() else [],
                  benchmark_metrics=read("benchmark_metrics") if (p/"benchmark_metrics.json").exists() else {})


def list_runs(root="storage"):
    path = Path(root) / "experiments.sqlite"
    if not path.exists():
        return pd.DataFrame()
    with sqlite3.connect(path) as db:
        return pd.read_sql_query("SELECT * FROM experiments ORDER BY created_at DESC", db)
