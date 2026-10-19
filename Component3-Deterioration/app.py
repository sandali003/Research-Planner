"""Component 3 web app + ML service: serves the trained models to the browser
page and to the Node backend (which stores the results in PostgreSQL).

Run:  .venv\\Scripts\\python -m uvicorn app:app --port 8002
Open: http://127.0.0.1:8002
"""
import os

# The training/predict scripts load files by relative path, so run from this folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

from typing import List, Optional

import joblib
import numpy as np
import pandas as pd

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from data_prep import PROBLEM_SYNONYMS, CONDITION_ORDER, load_inspections, load_service_data
from predict_deterioration import assess_vehicle, bundle as deterioration_bundle

condition_model = joblib.load("vehicle_condition_model.joblib")
solution_model = joblib.load("solution_prediction_model.joblib")
obd_bundle = joblib.load("obd_anomaly_model.joblib")


# --------------------------------------------------
# DROPDOWN OPTIONS (taken from the training data)
# --------------------------------------------------

_inspections = load_inspections()
_service = load_service_data()


def _history_items(series):
    items = series.str.split(";").explode().str.strip()
    return sorted(i for i in items.unique() if i)


OPTIONS = {
    "vehicle_models": sorted(_inspections["vehicle_model"].unique()),
    "components": sorted(_inspections["component"].unique()),
    "component_states": [s for s in reversed(CONDITION_ORDER)],
    "problems": sorted(_service["COMMON PROBLEM"].unique()),
    "service_history": _history_items(_service["SERVICE HISTORY"]),
}

# Per-inspection results from training: used for the age vs condition chart
# and for the age/mileage range the models have actually seen.
_history = pd.read_csv("reports/deterioration_results.csv")
TRAINED_RANGE = {
    "age_years": [float(_history["age_years"].min()), float(_history["age_years"].max())],
    "odometer_km": [float(_history["odometer_km"].min()), float(_history["odometer_km"].max())],
}

STATUS_ORDER = ["Normal", "Slightly high", "High"]

# Rule-based maintenance guidance shown next to components that are worse than expected
MAINTENANCE_ADVICE = {
    "Battery": "Load-test the battery and check the charging voltage; replace if it fails the test.",
    "Brakes": "Measure pad and disc thickness and check brake fluid; replace worn parts.",
    "Cooling_System": "Pressure-test the cooling system, check coolant level, hoses and radiator.",
    "Engine": "Run a full OBD-II scan, check compression and oil condition.",
    "Exhaust_System": "Inspect for leaks, corrosion and damaged hangers; check catalytic converter.",
    "Steering": "Check steering play, rack and tie-rod ends, and power-steering fluid.",
    "Suspension": "Inspect shock absorbers, bushes and ball joints; do a bounce test.",
    "Transmission": "Check transmission fluid level and colour; scan for shift-related codes.",
    "Tyres": "Measure tread depth, check for uneven wear and do a wheel alignment.",
}


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(title="AutoSense Component 3 API")


class VehicleInput(BaseModel):
    vehicle_model: str
    age_years: float = Field(ge=0, le=60)
    odometer_km: float = Field(ge=0, le=2_000_000)
    component: str
    component_state: str


class ServiceInput(BaseModel):
    service_history: str = ""
    common_problem: str = Field(min_length=1)


class ObdInput(BaseModel):
    engine_rpm: float
    engine_load: float
    coolant_temp: float


class ComponentCheck(BaseModel):
    component: str
    component_state: str


class AssessmentInput(BaseModel):
    vehicle_model: str
    age_years: float = Field(ge=0, le=60)
    odometer_km: float = Field(ge=0, le=2_000_000)
    components: List[ComponentCheck] = Field(min_length=1)
    obd: Optional[ObdInput] = None


def _obd_check(reading: ObdInput):
    model = obd_bundle["model"]
    row = pd.DataFrame([reading.model_dump()])[obd_bundle["features"]]
    return {
        "anomaly": bool(model.predict(row)[0] == -1),
        "anomaly_score": round(float(-model.score_samples(row)[0]), 3),
    }


@app.get("/")
def home():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


@app.get("/health")
def health():
    model_file = os.path.join(BASE_DIR, "deterioration_model.joblib")
    return {"status": "ok", "model_version": f"deterioration-{int(os.path.getmtime(model_file))}"}


@app.get("/api/options")
def options():
    return OPTIONS


@app.get("/api/metrics")
def metrics():
    return {
        "threshold": deterioration_bundle["threshold"],
        "typical_km_per_year": round(deterioration_bundle["typical_km_per_year"]),
        **deterioration_bundle["metrics"],
    }


@app.post("/api/deterioration")
def deterioration(vehicle: VehicleInput):
    return assess_vehicle(**vehicle.model_dump())


@app.post("/api/assess")
def assess(data: AssessmentInput):
    """Component-wise assessment for one vehicle (proposal section 4.1)."""
    components = []
    for check in data.components:
        result = assess_vehicle(data.vehicle_model, data.age_years, data.odometer_km,
                                check.component, check.component_state)
        components.append({"component": check.component, "component_state": check.component_state, **result})

    worst = min(components, key=lambda c: c["deterioration_deviation"])
    status = max((c["deterioration_status"] for c in components), key=STATUS_ORDER.index)
    km_per_year = data.odometer_km / max(data.age_years, 1)

    recommendations = [
        {"component": c["component"], "status": c["deterioration_status"],
         "advice": MAINTENANCE_ADVICE.get(c["component"], "Inspect this component.")}
        for c in sorted(components, key=lambda c: c["deterioration_deviation"])
        if c["deterioration_status"] != "Normal"
    ]

    # Reliability: say when inputs are outside what the models were trained on
    warnings = []
    for field, value in [("age_years", data.age_years), ("odometer_km", data.odometer_km)]:
        low, high = TRAINED_RANGE[field]
        if not low <= value <= high:
            label = "Age" if field == "age_years" else "Mileage"
            warnings.append(f"{label} is outside the training range ({low:,.1f}–{high:,.1f}); "
                            "the expected condition is less reliable.")

    obd = _obd_check(data.obd) if data.obd else None
    if obd and obd["anomaly"]:
        warnings.append("OBD-II reading is unusual compared with normal engine behaviour.")

    return {
        "status": status,
        "expected_condition": worst["expected_condition"],
        "observed_condition": round(float(np.mean([c["observed_condition"] for c in components])), 1),
        "worst_component": worst["component"],
        "worst_deviation": worst["deterioration_deviation"],
        "km_per_year": round(km_per_year),
        "typical_km_per_year": round(deterioration_bundle["typical_km_per_year"]),
        "threshold": deterioration_bundle["threshold"],
        "components": components,
        "recommendations": recommendations,
        "warnings": warnings,
        "obd": obd,
    }


@app.get("/api/expected-curve")
def expected_curve(vehicle_model: str, km_per_year: float):
    """Expected condition by age for a vehicle driven km_per_year."""
    ages = np.arange(0, 21, 0.5)
    rows = pd.DataFrame({"age_years": ages, "odometer_km": ages * km_per_year, "vehicle_model": vehicle_model})
    expected = deterioration_bundle["expected_model"].predict(rows[deterioration_bundle["baseline_features"]])
    return [{"age_years": float(a), "expected": round(float(e), 1)} for a, e in zip(ages, expected)]


@app.get("/api/history")
def history(vehicle_model: str):
    rows = _history[_history["vehicle_model"] == vehicle_model]
    return {
        "trained_range": TRAINED_RANGE,
        "points": rows[["age_years", "odometer_km", "inspection_score", "status"]].to_dict(orient="records"),
    }


@app.post("/api/condition")
def condition(vehicle: VehicleInput):
    row = pd.DataFrame([vehicle.model_dump()])
    probabilities = condition_model.predict_proba(row)[0]
    return {
        "predicted": str(condition_model.classes_[probabilities.argmax()]),
        "probabilities": {
            str(c): round(float(p) * 100, 1)
            for c, p in zip(condition_model.classes_, probabilities)
        },
    }


@app.post("/api/solution")
def solution(service: ServiceInput):
    # Clean the input the same way the training data was cleaned
    problem = service.common_problem.strip()
    record = pd.DataFrame([{
        "SERVICE HISTORY": service.service_history.strip().replace(",", ";"),
        "COMMON PROBLEM": PROBLEM_SYNONYMS.get(problem, problem),
    }])
    probabilities = solution_model.predict_proba(record)[0]
    top = probabilities.argsort()[::-1][:3]
    return {
        "solutions": [
            {"solution": str(solution_model.classes_[i]), "confidence": round(float(probabilities[i]) * 100, 1)}
            for i in top
        ]
    }


@app.post("/api/obd")
def obd(reading: ObdInput):
    return _obd_check(reading)


@app.get("/api/obd/vehicles")
def obd_vehicles():
    return pd.read_csv("reports/obd_vehicle_anomaly.csv").head(15).to_dict(orient="records")
