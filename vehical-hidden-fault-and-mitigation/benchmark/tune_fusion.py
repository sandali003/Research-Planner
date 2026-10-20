"""Tune the live system's fusion settings and write models/fusion_config.json.

Same procedure as the nested tuning in run_ablation.py, but on every
vehicle (out-of-fold by vehicle). expert_system.py reads the confidence
gate and obd_assessment.py reads the anomaly threshold from the file.
Delete the file to go back to the untuned behaviour.

Run (from the component folder):  python benchmark/tune_fusion.py
"""

from pathlib import Path
import json
import sys

import joblib
import numpy as np

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parent))
sys.path.insert(0, str(BENCH_DIR))

from fault_injection import load_normal_readings  # noqa: E402
from fusion_tuning import MAX_FALSE_ALARM_RATE, build_tuning_set, grid_search  # noqa: E402

MODEL_DIR = BENCH_DIR.parent / "models"
RESULTS_DIR = BENCH_DIR / "results"
SEED = 0


def main():
    classifier = joblib.load(MODEL_DIR / "autosense_fault_model.joblib")
    with open(MODEL_DIR / "model_metadata.json", encoding="utf-8") as f:
        classifier_features = json.load(f)["features"]

    base = load_normal_readings()
    oof_scores, tuning = build_tuning_set(base, classifier, classifier_features,
                                          np.random.default_rng(SEED), SEED)
    best, grid = grid_search(oof_scores, tuning)

    RESULTS_DIR.mkdir(exist_ok=True)
    grid.to_csv(RESULTS_DIR / "fusion_grid.csv", index=False)

    config = {
        "classifier_min_confidence": float(best["confidence_gate"]),
        "anomaly_threshold_percentile": float(best["threshold_percentile"]),
        "anomaly_threshold": float(best["anomaly_threshold"]),
        "threshold_rule": "percentile of out-of-fold anomaly scores (GroupKFold by vehicle)",
        "objective": (f"max macro F1 on injected faults (benchmark/fault_injection.py) "
                      f"with false alarm rate <= {MAX_FALSE_ALARM_RATE:.0%}"),
        "tuning_macro_f1": round(float(best["macro_f1"]), 4),
        "tuning_false_alarm_rate": round(float(best["false_alarm_rate"]), 4),
        "tuning_readings": len(tuning),
    }
    with open(MODEL_DIR / "fusion_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    untuned = grid[(grid["confidence_gate"] == 0.0) & (grid["threshold_percentile"] == 95)].iloc[0]
    print(json.dumps(config, indent=2))
    print(f"Untuned (gate 0, 95th pct): macro F1 {untuned['macro_f1']:.3f}, "
          f"false alarms {untuned['false_alarm_rate']:.3f}")


if __name__ == "__main__":
    main()
