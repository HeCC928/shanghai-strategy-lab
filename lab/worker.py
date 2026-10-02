import json
from pathlib import Path
import sys
import traceback
import os

from lab.jobs import write_status


class Cancelled(Exception):
    pass


def main(request_file):
    if os.environ.get("LAB_OFFLINE") == "1":
        from lab.offline import enable_offline
        enable_offline()
    path=Path(request_file).parent
    request=json.loads(Path(request_file).read_text(encoding="utf-8"))
    payload=request["payload"]
    def progress(value,message):
        if (path/"cancel").exists(): raise Cancelled()
        write_status(path,state="running",progress=float(value),message=message,pid=os.getpid())
    try:
        progress(0.,"开始处理")
        if request["kind"]=="run":
            from lab.config import Config
            from lab.data import Snapshot
            from lab.research import run_experiment
            from lab.store import save_result
            result=run_experiment(Config(**payload["config"]),Snapshot.load(payload["snapshot"]),progress)
            result.manifest["target_period_optimized"]=payload.get("target_period_optimized",False)
            progress(.99,"保存报告与实验")
            output=save_result(result,payload.get("output_root","storage"))
        elif request["kind"]=="search":
            from lab.config import Config
            from lab.data import Snapshot
            from lab.search import target_search
            output=target_search(Config(**payload["config"]),Snapshot.load(payload["snapshot"]),
                                 payload.get("candidates"),progress,payload.get("output_root","storage"))
        elif request["kind"]=="walkforward":
            from lab.config import Config
            from lab.data import Snapshot
            from lab.protocols import WalkForwardConfig
            from lab.walkforward import run_walkforward
            from lab.store import save_result
            result=run_walkforward(Config(**payload["config"]),Snapshot.load(payload["snapshot"]),
                                   WalkForwardConfig(**payload.get("protocol",{})),payload.get("candidates"),progress)
            progress(.99,"Saving rolling research")
            output=save_result(result,payload.get("output_root","storage"))
        elif request["kind"]=="download":
            from lab.providers import download_snapshot,attach_market
            snapshot=download_snapshot(**payload,progress=progress)
            progress(.99,"补充指数参考")
            try: snapshot=attach_market(snapshot)
            except Exception as exc: snapshot.manifest["limitations"].append("指数参考下载失败："+str(exc))
            output=snapshot.save()
        elif request["kind"]=="sensitivity":
            from lab.config import Config
            from lab.data import Snapshot
            from lab.sensitivity import run_sensitivity
            grid=run_sensitivity(Config(**payload["config"]),Snapshot.load(payload["snapshot"]),progress)
            output=path/"sensitivity.csv"
            grid.to_csv(output,index=False,encoding="utf-8-sig")
        else:
            raise ValueError("未知任务类型")
        write_status(path,state="completed",progress=1.,message="已完成",output=str(output.resolve()))
    except Cancelled:
        write_status(path,state="cancelled",message="已取消；成功下载缓存保留。")
    except Exception as exc:
        traceback.print_exc()
        write_status(path,state="failed",message=str(exc))


if __name__=="__main__":
    main(sys.argv[1])
