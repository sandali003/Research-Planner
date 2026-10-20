"""Load the saved models and check them on the same held-out test split used in training.

Run:  .venv\\Scripts\\python.exe check_models.py
"""

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split

import data
from train import SEED, metrics

MODEL_DIR = Path(__file__).resolve().parent / "models"


def main():
    master = data.load_master()
    _, test = train_test_split(master, test_size=0.2, random_state=SEED)
    y = test[data.TARGET].values

    meta = json.loads((MODEL_DIR / "model_meta.json").read_text())
    print("Saved metrics (model_meta.json):")
    for key in ("baseline", "condition_aware"):
        m = meta[key]
        print(f"  {key:16s} {m['model']:17s} MAE={m['test_MAE']:>10,.0f}  R2={m['test_R2']:.4f}")

    print(f"\nRe-checked now on {len(test)} test vehicles:")
    preds = {}
    for key in ("baseline", "condition_aware"):
        model = joblib.load(MODEL_DIR / f"valuation_{key}.joblib")
        preds[key] = model.predict(test)
        m = metrics(y, preds[key])
        print(f"  {key:16s} MAE={m['MAE']:>10,.0f}  RMSE={m['RMSE']:>10,.0f}  "
              f"R2={m['R2']:.4f}  MAPE={m['MAPE_%']:.2f}%")

    sample = pd.DataFrame({
        "vehicle_id": test.vehicle_id.values,
        "model": test.vehicle_model.values,
        "year": test.manufacture_year.values,
        "health": test.health_score.values,
        "actual_lkr": y,
        "baseline_lkr": preds["baseline"].round(-3),
        "condition_lkr": preds["condition_aware"].round(-3),
    }).head(10)
    sample["condition_error_%"] = ((sample.condition_lkr - sample.actual_lkr) / sample.actual_lkr * 100).round(1)
    print("\nSample predictions vs actual price:")
    print(sample.to_string(index=False, float_format=lambda v: f"{v:,.0f}" if abs(v) > 1000 else f"{v:.1f}"))


if __name__ == "__main__":
    main()
