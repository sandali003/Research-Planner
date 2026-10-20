"""Component 4 web server: valuation, maintenance recommendations and repair scenarios.

Run:  .venv\\Scripts\\python.exe app.py
Then open http://127.0.0.1:8001 (opens automatically).

API (for the dashboard and for the other AutoSense components):
  GET  /api/summary                      model metrics, comparison table, feature importance
  GET  /api/vehicles?model=Axio          vehicles in the dataset (summary list)
  GET  /api/vehicles/{id}?repairs=0,2    one vehicle: inputs, faults and full assessment
  POST /api/assess                       assess a new vehicle from Component 1/2/3 outputs
"""

import json
import threading
import webbrowser
from pathlib import Path
from typing import List, Literal, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

import data
from engine import Component4Engine

ROOT = Path(__file__).resolve().parent
HOST, PORT = "127.0.0.1", 8001

app = FastAPI(title="AutoSense Component 4 API")
engine = Component4Engine()
master = data.load_master()
events = data.load_fault_events()
meta = json.loads((ROOT / "models" / "model_meta.json").read_text())


def records(df):
    """DataFrame -> JSON-safe list of dicts (numpy types converted)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def faults_for(vehicle_id):
    return records(events.loc[events.vehicle_id == vehicle_id, ["fault_code", "severity"]])


def parse_repairs(repairs):
    if repairs is None:
        return None
    try:
        return [int(i) for i in repairs.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(400, "repairs must be a comma-separated list of fault positions, e.g. 0,2")


def build_index():
    """Reuse the dashboard markup/CSS from web/template.html, swapping its embedded-data script for app.js."""
    template = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
    markup = template[:template.index("<script>")]
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
            + markup + "<script src=\"/app.js\"></script></html>")


INDEX_HTML = build_index()


@app.get("/", include_in_schema=False)
def index():
    return HTMLResponse(INDEX_HTML)


@app.get("/app.js", include_in_schema=False)
def app_js():
    return FileResponse(ROOT / "web" / "app.js", media_type="application/javascript")


@app.get("/api/summary")
def summary():
    return {
        "meta": meta,
        "results": records(pd.read_csv(ROOT / "reports" / "valuation_results.csv")),
        "importance": records(pd.read_csv(ROOT / "reports" / "condition_aware_feature_importance.csv")),
    }


@app.get("/api/vehicles")
def list_vehicles(model: Optional[str] = None):
    df = master if not model else master[master.vehicle_model == model]
    return records(df[["vehicle_id", "vehicle_model", "manufacture_year", "fault_count"]])


@app.get("/api/vehicles/{vehicle_id}")
def vehicle(vehicle_id: str, repairs: Optional[str] = None):
    row = master[master.vehicle_id == vehicle_id]
    if row.empty:
        raise HTTPException(404, f"Vehicle {vehicle_id} not found")
    v = records(row)[0]
    faults = faults_for(vehicle_id)
    return {"vehicle": v, "faults": faults,
            "assessment": engine.assess(v, faults, parse_repairs(repairs))}


class Fault(BaseModel):
    fault_code: str = Field(examples=["P0301"])
    severity: Literal["Low", "Medium", "High", "Critical"]


class AssessRequest(BaseModel):
    vehicle_id: Optional[str] = None
    vehicle_model: str = Field(examples=["Axio"])
    vehicle_age: int = Field(ge=0, examples=[11])
    mileage_km: float = Field(ge=0, examples=[95000])
    engine_capacity_cc: int = Field(examples=[1496])
    fuel_type: str = Field(examples=["Hybrid"])
    transmission: str = Field(examples=["e-CVT"])
    health_score: float = Field(ge=0, le=100, description="Component 1 output", examples=[74.5])
    deterioration_deviation: float = Field(description="Component 3 output", examples=[0.3])
    deterioration_class: Literal["Better than expected", "As expected", "Worse than expected"] = Field(
        description="Component 3 output", examples=["As expected"])
    faults: List[Fault] = Field(default_factory=list, description="Component 2 output")
    repair_indices: Optional[List[int]] = None


@app.post("/api/assess")
def assess(req: AssessRequest):
    faults = [f.model_dump() for f in req.faults]
    vehicle = req.model_dump(exclude={"faults", "repair_indices"})
    vehicle["fault_count"] = len(faults)
    worst = max((data.SEVERITY_LEVEL[f["severity"]] for f in faults), default=0)
    vehicle["severity"] = data.LEVEL_SEVERITY[worst]
    return engine.assess(vehicle, faults, req.repair_indices)


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"AutoSense Component 4 running at {url}  (API docs: {url}/docs)")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=HOST, port=PORT)
