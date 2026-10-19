"""REST API for the Hidden Fault Prediction and Mitigation component.

The Node backend sends one window of processed sensor data and gets
back the predicted faults, confidence, severity and mitigation plan
as JSON.

Run (from this folder):  uvicorn api:app --port 8002
"""

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fault_service import HiddenFaultService

app = FastAPI(title="AutoSense Hidden Fault Prediction and Mitigation")
service = HiddenFaultService()


class FaultInputs(BaseModel):
    """One window of fused OBD-II + IoT sensor data. All fields optional;
    each model runs only when its inputs are present."""

    engine_rpm: Optional[float] = Field(None, ge=0, le=10000)
    engine_load_pct: Optional[float] = Field(None, ge=0, le=100)
    coolant_temp_c: Optional[float] = Field(None, ge=-40, le=150)
    engine_temp_c: Optional[float] = Field(None, ge=-40, le=150)
    battery_voltage_v: Optional[float] = Field(None, ge=0, le=20)
    vibration_x_g: Optional[float] = Field(None, ge=-4, le=4)
    vibration_y_g: Optional[float] = Field(None, ge=-4, le=4)
    vibration_z_g: Optional[float] = Field(None, ge=-4, le=4)
    vehicle_model: Optional[str] = Field(None, max_length=60)
    dtc_codes: List[str] = Field(default_factory=list, max_length=20)


@app.get("/health")
def health():
    return {"status": "ok", "model_versions": service.model_versions}


@app.post("/predict")
def predict(inputs: FaultInputs):
    try:
        return service.assess(inputs.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
