"""Create an explicitly synthetic, offline experiment for a source-only checkout."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare(output_root):
    from lab.offline import enable_offline
    enable_offline()
    from lab.config import Config
    from lab.demo import synthetic_snapshot
    from lab.research import run_experiment
    from lab.store import save_result

    output_root = Path(output_root).resolve()
    snapshot = synthetic_snapshot(count=12, start="2023-01-02", end="2026-06-30")
    snapshot.instruments["name"] = [f"Synthetic sample {i+1:02d}" for i in range(12)]
    # A synthetic equal-weight reference supports the optional risk-control switches.
    prices = snapshot.bars.pivot(index="date", columns="symbol", values="adj_close")
    reference = prices.div(prices.iloc[0]).mean(axis=1).mul(1000)
    snapshot.market = reference.rename("close").reset_index()
    snapshot.manifest.update(
        requested=12,
        label="Synthetic offline demo — not historical market performance",
        market_source="Synthetic equal-weight price reference; not the SSE Composite",
        limitations=[
            "All prices and the market reference are synthetic; symbol codes are placeholders.",
            "Weekday calendar is synthetic and does not model exchange holidays.",
            "For software demonstrations only; these returns are not investment evidence.",
        ],
    )
    snapshot_path = snapshot.save(output_root / "snapshots")
    config = Config(strategy="threshold", start="2025-07-01", end="2026-06-30", threshold_ma=30)
    print("Preparing a SYNTHETIC demo. No market data is downloaded.", flush=True)
    result = run_experiment(config, snapshot)
    result.manifest.update(study="Synthetic functional demonstration — not market performance", public_demo=True)
    run_path = save_result(result, output_root)
    details = {"source": "synthetic", "snapshot": snapshot_path.name, "run": run_path.name}
    print(json.dumps(details, indent=2))
    print("Ready. Start the app and select this saved experiment. It does not reproduce the featured 1.48 Sharpe.")
    return details


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "storage")
    args = parser.parse_args()
    prepare(args.output_root)
