"""Single-user background jobs with persistent progress and cooperative cancellation."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import psutil
import sqlite3
from filelock import FileLock
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parents[1]


@contextmanager
def status_database(path):
    db=sqlite3.connect(Path(path).parent/"jobs.sqlite",timeout=15)
    try:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, status_json TEXT NOT NULL)")
            yield db
    finally:
        db.close()


def write_status(path,**values):
    p=Path(path)/"status.json"
    current=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    current.update(values,updated_at=datetime.now(timezone.utc).isoformat())
    with status_database(path) as db:
        db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?)",(Path(path).name,json.dumps(current,ensure_ascii=False)))
    tmp=p.with_suffix(".tmp")
    tmp.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding="utf-8")
    for attempt in range(50):
        try:
            tmp.replace(p)
            break
        except PermissionError:
            if attempt==49: raise
            time.sleep(.01)


def read_job(path):
    path=Path(path)
    with status_database(path) as db:
        saved=db.execute("SELECT status_json FROM jobs WHERE job_id=?",(path.name,)).fetchone()
    state=json.loads(saved[0] if saved else (path/"status.json").read_text(encoding="utf-8"))
    if not state.get("pid") and (path/"pid").exists(): state["pid"]=int((path/"pid").read_text())
    if state["state"] in ("queued","running","cancelling") and state.get("pid"):
        try:
            p=psutil.Process(state["pid"])
            live=p.is_running() and str(path.resolve()/"request.json") in p.cmdline()
        except psutil.NoSuchProcess: live=False
        except psutil.AccessDenied: live=True
        if not live:
            state.update(state="interrupted",message="工作进程已结束，未产生完整结果；成功下载缓存保留。")
    return state


def start_job(kind,payload,root="storage/jobs"):
    root=Path(root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    with FileLock(str(root/"start.lock"),timeout=10):
        return _start_job(kind,payload,root)


def _start_job(kind,payload,root):
    for p in root.glob("*/status.json"):
        if read_job(p.parent)["state"] in ("queued","running","cancelling"):
            raise RuntimeError("已有任务在运行，请等待完成或取消；可以继续查看已保存实验。")
    path=root/uuid.uuid4().hex[:16]
    path.mkdir()
    request=path/"request.json"
    request.write_text(json.dumps({"kind":kind,"payload":payload},ensure_ascii=False),encoding="utf-8")
    write_status(path,state="queued",progress=0.,message="正在启动",kind=kind)
    with (path/"worker.log").open("w",encoding="utf-8") as log:
        process=subprocess.Popen([sys.executable,"-m","lab.worker",str(request)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0,
                                 env={**os.environ,"PYTHONIOENCODING":"utf-8"})
    # Separate PID file avoids a parent/worker read-modify-write race on status.json.
    (path/"pid").write_text(str(process.pid))
    return str(path)


def cancel_job(path):
    (Path(path)/"cancel").touch()


def running_jobs(root="storage/jobs"):
    result=[]
    for p in sorted(Path(root).glob("*/status.json"),key=lambda p:p.stat().st_mtime,reverse=True):
        state=read_job(p.parent)
        result.append({**state,"path":str(p.parent.resolve())})
    return result
