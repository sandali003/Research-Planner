"""Thin FastAPI wrapper exposing health_assessment.assess() to the Node backend.

Run (from repo root):  uvicorn server:app --app-dir ml-service --port 8001
"""
import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

MODEL_DIR = Path(__file__).resolve().parent.parent / "ai-vehicle-health-assessment"
sys.path.insert(0, str(MODEL_DIR))

import health_assessment  # noqa: E402

app = FastAPI(title="AutoSense ML service")


def _model_version() -> str:
    summary = MODEL_DIR / "models" / "health_summary.json"
    mtime = int(summary.stat().st_mtime) if summary.exists() else 0
    return f"health_overall-{mtime}"


class Features(BaseModel):
    ds18b20_temp_c: float
    battery_voltage_v: float
    vibration_rms_g: float
    vibration_peak_g: float
    dtc_codes: Optional[str] = ""
    engine_rpm: Optional[float] = None
    engine_load_pct: Optional[float] = None


@app.get("/health")
def health():
    return {"status": "ok", "model_version": _model_version()}


@app.post("/predict")
def predict(features: Features):
    result = health_assessment.assess(features.model_dump())
    result["model_version"] = _model_version()
    return json.loads(json.dumps(result, default=float))
