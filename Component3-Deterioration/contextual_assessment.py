"""Component 3, step 3: contextual deterioration from the real-data baseline.

For a vehicle (model, age, mileage) and its inspected components, places the
observed condition in the distribution of comparable vehicles learned from
UK MOT data (train_expected_condition.py) and reports:

  percentile         share of comparable cars in a worse condition (mid-rank).
                     "Worse than X% of comparable cars" = 1 - percentile.
  effective age      condition-equivalent age: the age at which a car driven
                     like this one (same km per year) is typically, i.e. at the
                     50th percentile, in this condition. Searched between 1 and
                     25 years; a defect that is not typical at any age in the
                     data is reported as "older than 25" (bound = "older").
  age gap            effective age - real age (+5 = five years "older" than it is)
  status             statistical, not a fixed score threshold:
                       High          worst 10% of comparable cars
                       Slightly high worst 10-25%
                       Normal        otherwise
                     The vehicle status is the worst of the overall result and
                     its components (one accelerated component flags the car).

Inspection states map to the DVSA defect categories used for the grades:
Good -> no defect, Fair -> wear (advisory), Poor -> minor defect,
Critical -> major / dangerous defect. Only components the MOT inspects have a
real-data baseline: brakes, suspension, steering, tyres and exhaust.
Vitz uses the Yaris baseline; Axio, Allion and Premio use the Corolla baseline.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from mot_condition import COMPONENT_GRADES, OVERALL_GRADES, PLATFORM

MODEL_FILE = Path(__file__).resolve().parent / "models" / "expected_condition_model.joblib"

STATE_TO_GRADE = {"Good": 4, "Fair": 3, "Poor": 2, "Critical": 1}
COMPONENT_GROUP = {
    "Brakes": "brakes", "Suspension": "suspension", "Steering": "steering",
    "Tyres": "tyres", "Exhaust_System": "emissions_leaks",
}
HIGH_PERCENTILE, SLIGHT_PERCENTILE = 0.10, 0.25

# Median engine size per platform in the training data (used when not given)
DEFAULT_ENGINE_CC = {"Yaris": 1329, "Corolla": 1598}
DEFAULT_FUEL = "PE"
FUEL_CODES = {"petrol": "PE", "diesel": "DI", "hybrid": "HY", "PE": "PE", "DI": "DI", "HY": "HY"}
# 1st-99th percentile of the training data; outside it the baseline is extrapolated
DATA_RANGE = {"age_years": (3.0, 23.8), "odometer_km": (11_000, 296_000)}

# Effective age is only searched inside the real data (99th percentile ~24 years);
# beyond it the result is reported as "older than 25" / "younger than 1"
AGE_GRID = np.round(np.arange(1, 25.01, 0.25), 2)
STATUS_ORDER = ["Normal", "Slightly high", "High"]
CURVE_AGES = np.arange(1, 26)

_bundle = joblib.load(MODEL_FILE)
MODELS = _bundle["models"]


def _status(percentile):
    if percentile <= HIGH_PERCENTILE:
        return "High"
    if percentile <= SLIGHT_PERCENTILE:
        return "Slightly high"
    return "Normal"


def _rows(platform, fuel, engine_cc, ages, km_per_year):
    ages = np.asarray(ages, dtype=float)
    return pd.DataFrame({"platform": platform, "fuel_type": fuel, "engine_cc": float(engine_cc),
                         "age_years": ages, "odometer_km": ages * km_per_year})


def _percentile(probs, levels, grade):
    """Share of comparable cars in a worse condition than `grade` (mid-rank), per row of probs."""
    i = levels.index(grade)
    return probs[:, :i].sum(axis=1) + 0.5 * probs[:, i]


def _effective_age(model, levels, grade, platform, fuel, engine_cc, km_per_year):
    """Age at which this grade is typical (50th percentile) for a car driven km_per_year."""
    p = _percentile(model.predict_proba(_rows(platform, fuel, engine_cc, AGE_GRID, km_per_year)), levels, grade)
    if p[0] >= 0.5:
        return float(AGE_GRID[0]), "younger"
    if p[-1] < 0.5:
        return float(AGE_GRID[-1]), "older"
    i = int(np.argmax(p >= 0.5))
    a0, a1, p0, p1 = AGE_GRID[i - 1], AGE_GRID[i], p[i - 1], p[i]
    return float(a0 + (0.5 - p0) / max(p1 - p0, 1e-9) * (a1 - a0)), "within"


def _assess(target, grade, grade_names, platform, fuel, engine_cc, age, km, km_per_year):
    model = MODELS[target]
    levels = sorted(grade_names)
    probs = model.predict_proba(_rows(platform, fuel, engine_cc, [age], km_per_year))
    percentile = float(_percentile(probs, levels, grade)[0])
    effective, bound = _effective_age(model, levels, grade, platform, fuel, engine_cc, km_per_year)
    return {
        "observed_grade": grade,
        "observed_label": grade_names[grade],
        "expected_grade": round(float(probs[0] @ np.array(levels)), 2),
        "grade_distribution": {grade_names[k]: round(float(p), 3) for k, p in zip(levels, probs[0])},
        "percentile": round(percentile, 3),
        "worse_than_pct": round((1 - percentile) * 100),
        "effective_age": round(effective, 1),
        "effective_age_bound": bound,
        "age_gap": round(effective - age, 1),
        "status": _status(percentile),
    }


def condition_curve(platform, fuel, engine_cc, km_per_year):
    """Share of comparable cars in each overall grade, by age (for the chart)."""
    levels = sorted(OVERALL_GRADES)
    probs = MODELS["grade"].predict_proba(_rows(platform, fuel, engine_cc, CURVE_AGES, km_per_year))
    return [{"age_years": int(a), **{OVERALL_GRADES[k]: round(float(p), 4) for k, p in zip(levels, row)}}
            for a, row in zip(CURVE_AGES, probs)]


def assess_contextual(vehicle_model, age_years, odometer_km, components, fuel_type=None, engine_cc=None):
    """Contextual assessment for one vehicle, or None when the model has no real-data baseline.

    components: [{"component": "Brakes", "component_state": "Poor"}, ...]
    """
    platform = PLATFORM.get(vehicle_model)
    if platform is None:
        return None
    fuel = FUEL_CODES.get(str(fuel_type).strip(), DEFAULT_FUEL) if fuel_type else DEFAULT_FUEL
    engine_cc = engine_cc or DEFAULT_ENGINE_CC[platform]
    age = max(float(age_years), 0.5)
    km_per_year = float(odometer_km) / age

    notes = []
    if vehicle_model != platform:
        notes.append(f"{vehicle_model} is not sold in the UK; the {platform} baseline is used "
                     "(same platform and engine family).")
    for field, value in (("age_years", age), ("odometer_km", float(odometer_km))):
        low, high = DATA_RANGE[field]
        if not low <= value <= high:
            label = "Age" if field == "age_years" else "Mileage"
            notes.append(f"{label} is outside most of the real data ({low:,.0f}-{high:,.0f}); "
                         "the comparison is less certain.")

    results, not_covered = [], []
    for check in components:
        group = COMPONENT_GROUP.get(check["component"])
        if group is None:
            not_covered.append(check["component"])
            continue
        grade = STATE_TO_GRADE[check["component_state"]]
        results.append({"component": check["component"], "component_state": check["component_state"],
                        "mot_group": group,
                        **_assess(f"grade_{group}", grade, COMPONENT_GRADES, platform, fuel,
                                  engine_cc, age, odometer_km, km_per_year)})
    if not_covered:
        notes.append("No real-data baseline for " + ", ".join(c.replace("_", " ").lower() for c in not_covered)
                     + " (the MOT does not inspect them); they use the inspection-data model only.")
    if not results:
        return {"available": False, "platform": platform, "components": [], "notes": notes}

    # Vehicle level: the worst inspected component sets the overall grade, as in the MOT
    worst_component_grade = min(r["observed_grade"] for r in results)
    overall = _assess("grade", worst_component_grade + 1, OVERALL_GRADES, platform, fuel,
                      engine_cc, age, odometer_km, km_per_year)
    worst = min(results, key=lambda r: r["percentile"])
    status = max([overall["status"]] + [r["status"] for r in results], key=STATUS_ORDER.index)

    return {
        "available": True,
        "method": "Probabilistic age- and mileage-adjusted baseline (UK MOT 2023, Toyota)",
        "platform": platform,
        "fuel_type": fuel,
        "engine_cc": float(engine_cc),
        "age_years": round(age, 2),
        "km_per_year": round(km_per_year),
        "overall": overall,
        "status": status,
        "worst_component": worst["component"],
        "components": sorted(results, key=lambda r: r["percentile"]),
        "curve": condition_curve(platform, fuel, engine_cc, km_per_year),
        "thresholds": {"High": HIGH_PERCENTILE, "Slightly high": SLIGHT_PERCENTILE},
        "notes": notes,
    }
