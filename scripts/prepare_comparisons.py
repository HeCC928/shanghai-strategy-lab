"""Save declared comparisons without searching or changing the accepted case."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.config import Config
from lab.data import Snapshot
from lab.research import run_experiment
from lab.store import save_result

def main():
    path = ROOT / "configs/showcase.json"
    showcase = json.loads(path.read_text())
    base = json.loads((ROOT / "storage/runs" / showcase["featured_run_id"] / "config.json").read_text())
    snapshot = Snapshot.load(ROOT / "storage/snapshots" / showcase["snapshot_id"])
    cases = [
        ("default_threshold", "Original 20-session threshold", {"threshold_ma": 20}),
        ("original_momentum", "Original momentum rule", {"strategy": "momentum"}),
        ("trend_risk", "Threshold + market trend filter", {"market_filter": True}),
        ("volatility_risk", "Threshold + volatility allocation", {"volatility_control": True}),
    ]
    for key, label, changes in cases:
        if key in showcase.get("comparisons", {}):
            continue
        print(label, flush=True)
        result = run_experiment(Config(**{**base, **changes}), snapshot)
        result.manifest.update(target_period_optimized=True, study="Declared retrospective comparison", comparison_label=label)
        saved = save_result(result, ROOT / "storage")
        showcase.setdefault("comparisons", {})[key] = {"run_id": saved.name, "label": label, "changes": changes}
        path.write_text(json.dumps(showcase, indent=2), encoding="utf-8")
        print(json.dumps({"run": saved.name, "metrics": result.metrics}), flush=True)

if __name__ == "__main__":
    main()
