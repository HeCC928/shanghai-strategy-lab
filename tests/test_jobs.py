import time
from lab.config import Config
from lab.demo import synthetic_snapshot
from lab.jobs import start_job,read_job,cancel_job


def test_background_cancel_keeps_snapshot(tmp_path):
    snapshot=synthetic_snapshot(2).save(tmp_path/"snapshots")
    job=start_job("run",{"snapshot":str(snapshot.resolve()),"config":Config().model_dump(mode="json"),"output_root":str(tmp_path)},root=tmp_path/"jobs")
    cancel_job(job)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        state=read_job(job)
        if state["state"] in ("completed","failed","cancelled","interrupted"): break
        time.sleep(.1)
    assert state["state"]=="cancelled",state
    assert (snapshot/"manifest.json").exists()
