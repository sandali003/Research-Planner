"""Component 4 value-uplift API (real-data models).

POST /api/value-uplift   personalised plan: which repairs to do before selling and how
                          much they could add to the price (value_uplift.py)
GET  /health

Run (from component4):  .venv\\Scripts\\python -m uvicorn api:app --app-dir real --port 8004
"""

from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from value_uplift import ValueUpliftEngine

app = FastAPI(title="AutoSense Component 4: value uplift")
engine = ValueUpliftEngine()


class Vehicle(BaseModel):
    model: str = Field(min_length=1, max_length=40)
    age_years: float = Field(ge=0, le=45)
    mileage_km: float = Field(ge=0, le=600_000)
    engine_cc: Optional[float] = Field(None, ge=600, le=6000)
    fuel_type: Optional[Literal["petrol", "hybrid", "diesel"]] = None
    transmission: Optional[str] = None
    body_type: Optional[str] = None


class ContextualComponent(BaseModel):
    component: str
    mot_group: str
    observed_grade: int = Field(ge=1, le=4)


class ContextualOverall(BaseModel):
    grade_distribution: dict


class Contextual(BaseModel):
    """The 'contextual' block of a Component 3 assessment."""
    overall: ContextualOverall
    components: List[ContextualComponent]


class Fault(BaseModel):
    fault: str
    severity: Optional[str] = None


class UpliftRequest(BaseModel):
    vehicle: Vehicle
    contextual: Contextual
    faults: List[Fault] = []
    budget_lkr: Optional[float] = Field(None, ge=0)
    sell_within_days: Optional[int] = Field(None, ge=0, le=365)
    buyer: Literal["private", "dealer"] = "private"


@app.get("/health")
def health():
    return {"status": "ok", "models": {"valuation": engine.valuation["model_name"],
                                       "condition_effect": engine.effect["model_name"]}}


@app.post("/api/value-uplift")
def value_uplift(req: UpliftRequest):
    if not req.contextual.components:
        raise HTTPException(422, "Component 3 result has no MOT-inspected components (brakes, suspension, "
                                 "steering, tyres, exhaust); no condition-based value can be estimated.")
    return engine.recommend(
        req.vehicle.model_dump(), req.contextual.model_dump(), [f.model_dump() for f in req.faults],
        budget_lkr=req.budget_lkr, sell_within_days=req.sell_within_days, buyer=req.buyer,
    )
