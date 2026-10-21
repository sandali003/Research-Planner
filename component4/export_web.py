"""Export the trained linear valuation models, rules, costs and vehicles to JSON for the web page."""

import json
from pathlib import Path

import joblib
import pandas as pd

import data

ROOT = Path(__file__).resolve().parent


def linear_params(pipe):
    pre = pipe.named_steps["pre"]
    reg = pipe.named_steps["model"].regressor_
    scaler, encoder = pre.named_transformers_["num"], pre.named_transformers_["cat"]
    num_cols, cat_cols = pre.transformers_[0][2], pre.transformers_[1][2]
    n = len(num_cols)
    coef = reg.coef_.tolist()
    cats, i = {}, n
    for col, values in zip(cat_cols, encoder.categories_):
        cats[col] = {str(v): coef[i + j] for j, v in enumerate(values)}
        i += len(values)
    return {
        "intercept": float(reg.intercept_),
        "numeric": [{"col": c, "mean": float(m), "scale": float(s), "coef": coef[k]}
                    for k, (c, m, s) in enumerate(zip(num_cols, scaler.mean_, scaler.scale_))],
        "categorical": cats,
    }


def main():
    meta = json.loads((ROOT / "models" / "model_meta.json").read_text())
    master = data.load_master()
    events = data.load_fault_events()
    cols = ["vehicle_id", "vehicle_model", "manufacture_year", "vehicle_age", "mileage_km", "fuel_type",
            "transmission", "engine_capacity_cc", "health_score", "fault_count", "severity",
            "deterioration_deviation", "deterioration_class", "listing_price_lkr"]
    out = {
        "meta": meta,
        "models": {
            "baseline": linear_params(joblib.load(ROOT / "models" / "valuation_baseline.joblib")),
            "condition": linear_params(joblib.load(ROOT / "models" / "valuation_condition_aware.joblib")),
        },
        "vehicles": master[cols].values.tolist(),
        "vehicleCols": cols,
        "faults": events[["vehicle_id", "fault_code", "severity"]].values.tolist(),
        "rules": data.load_rules().where(lambda d: d.notna(), None).to_dict("records"),
        "costs": data.load_cost_lookup()[["vehicle_model", "repair_type", "typical_total_cost_lkr",
                                          "min_total_cost_lkr", "max_total_cost_lkr"]].values.tolist(),
        "results": pd.read_csv(ROOT / "reports" / "valuation_results.csv").round(4).to_dict("records"),
        "importance": pd.read_csv(ROOT / "reports" / "condition_aware_feature_importance.csv").round(0).to_dict("records"),
        # Reference predictions to check the JavaScript port against.
        "check": {
            vid: {k: float(joblib.load(ROOT / "models" / f"valuation_{f}.joblib")
                           .predict(master[master.vehicle_id == vid])[0])
                  for k, f in (("baseline", "baseline"), ("condition", "condition_aware"))}
            for vid in ("M4TP00002", "M4TP01324")
        },
    }
    (ROOT / "web").mkdir(exist_ok=True)
    (ROOT / "web" / "c4_data.json").write_text(json.dumps(out, separators=(",", ":"), default=str))
    print("wrote web/c4_data.json", (ROOT / "web" / "c4_data.json").stat().st_size, "bytes")


if __name__ == "__main__":
    main()


def build_page():
    """Inject the exported JSON into web/template.html -> web/autosense_c4.html."""
    web = ROOT / "web"
    html = (web / "template.html").read_text(encoding="utf-8")
    payload = (web / "c4_data.json").read_text(encoding="utf-8").replace("</", r"<\/")
    (web / "autosense_c4.html").write_text(html.replace("__C4_DATA__", payload), encoding="utf-8")
    print("wrote web/autosense_c4.html")


if __name__ == "__main__":
    build_page()
