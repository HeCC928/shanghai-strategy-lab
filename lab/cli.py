import argparse
import json
from pathlib import Path

from lab.config import Config
from lab.data import Snapshot
from lab.demo import synthetic_snapshot
from lab.engine import run_backtest


def main():
    p = argparse.ArgumentParser(description="沪A策略研究平台")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    market=sub.add_parser("market")
    market.add_argument("snapshot")
    download = sub.add_parser("download")
    download.add_argument("--count", type=int, default=12)
    download.add_argument("--symbols", default="")
    download.add_argument("--source", choices=["akshare", "baostock"], default="akshare")
    download.add_argument("--start", default="2017-01-01")
    download.add_argument("--end", default="2025-03-07")
    run = sub.add_parser("run")
    run.add_argument("snapshot")
    run.add_argument("--config")
    run.add_argument("--strategy", default="threshold")
    args = p.parse_args()
    if args.command == "demo":
        print(synthetic_snapshot().save())
    elif args.command == "market":
        from lab.providers import attach_market
        print(attach_market(Snapshot.load(args.snapshot)).save())
    elif args.command == "download":
        from lab.providers import download_snapshot
        s = download_snapshot(symbols=args.symbols.split(",") if args.symbols else None, count=args.count,
                              source=args.source, start=args.start, end=args.end,
                              progress=lambda x, text: print(text, flush=True))
        print(s.save())
    else:
        import yaml
        from lab.store import save_result
        c = Config(**yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))) if args.config else Config(strategy=args.strategy)
        from lab.research import run_experiment
        r = run_experiment(c, Snapshot.load(args.snapshot))
        print(save_result(r))
        print(json.dumps(r.metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
