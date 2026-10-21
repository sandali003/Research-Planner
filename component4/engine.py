"""Component 4 inference: valuation, maintenance recommendations, repair cost and repair scenarios.

Input is one vehicle record (market fields + Component 1/2/3 outputs) and its list of detected
fault codes with severity. Run directly for a demo on a vehicle from the dataset:

    .venv\\Scripts\\python.exe engine.py [vehicle_id]
"""

import json
import sys
from pathlib import Path

import joblib
import pandas as pd

import data

MODEL_DIR = Path(__file__).resolve().parent / "models"


class Component4Engine:
    def __init__(self):
        self.baseline = joblib.load(MODEL_DIR / "valuation_baseline.joblib")
        self.condition = joblib.load(MODEL_DIR / "valuation_condition_aware.joblib")
        self.rules = data.load_rules().set_index("fault_code")
        self.costs = data.load_cost_lookup().set_index(["vehicle_model", "repair_type"])

    def _value(self, vehicle, model):
        return float(model.predict(pd.DataFrame([vehicle]))[0])

    def _repair_cost(self, vehicle_model, repair_type):
        try:
            row = self.costs.loc[(vehicle_model, repair_type)]
        except KeyError:
            return None
        return {"typical": int(row.typical_total_cost_lkr), "min": int(row.min_total_cost_lkr),
                "max": int(row.max_total_cost_lkr)}

    @staticmethod
    def _after_repair(vehicle, remaining_faults):
        """Vehicle record with only `remaining_faults` still present (C2 features updated)."""
        after = dict(vehicle)
        after["fault_count"] = len(remaining_faults)
        levels = [data.SEVERITY_LEVEL[f["severity"]] for f in remaining_faults]
        after["severity_level"] = max(levels, default=0)
        after["severity"] = data.LEVEL_SEVERITY[after["severity_level"]]
        return after

    def assess(self, vehicle, faults, repair_indices=None):
        """vehicle: dict of master fields; faults: list of {"fault_code", "severity"}.

        repair_indices: positions in `faults` to include in the repair plan (default: all).
        """
        vehicle = dict(vehicle)
        vehicle["severity_level"] = data.SEVERITY_LEVEL[vehicle.get("severity") or "None"]

        missing = [c for c in self._required_fields() if pd.isna(vehicle.get(c))]
        if missing:
            raise ValueError(f"Missing required inputs: {missing}")

        baseline_value = self._value(vehicle, self.baseline)
        condition_value = self._value(vehicle, self.condition)

        recommendations = []
        for index, fault in enumerate(faults):
            if fault["fault_code"] not in self.rules.index:
                recommendations.append({**fault, "fault_index": index, "estimated_cost_lkr": None,
                                        "action": "Unknown fault code - refer to a mechanic",
                                        "priority_score": data.SEVERITY_LEVEL[fault["severity"]] * 10})
                continue
            rule = self.rules.loc[fault["fault_code"]]
            cost = self._repair_cost(vehicle["vehicle_model"], rule.primary_repair_type)
            remaining = [f for f in faults if f is not fault]
            value_after = self._value(self._after_repair(vehicle, remaining), self.condition)
            gain = value_after - condition_value
            recommendations.append({
                "fault_index": index,
                "fault_code": fault["fault_code"],
                "detected_problem": rule.detected_problem,
                "component": rule.component,
                "severity": fault["severity"],
                "rule_priority": rule.repair_priority,
                "action": rule.recommended_maintenance,
                "repair_type": rule.primary_repair_type,
                "alternative_repair": None if pd.isna(rule.secondary_repair_type) else rule.secondary_repair_type,
                "estimated_cost_lkr": cost,
                "estimated_value_change_lkr": round(gain),
                # Safety first: detected severity dominates, then the rule's priority.
                "priority_score": data.SEVERITY_LEVEL[fault["severity"]] * 10
                                  + data.PRIORITY_LEVEL[rule.repair_priority],
            })
        recommendations.sort(key=lambda r: r["priority_score"], reverse=True)
        for rank, rec in enumerate(recommendations, 1):
            rec["rank"] = rank

        value_all_fixed = self._value(self._after_repair(vehicle, []), self.condition)
        total_cost = sum(r["estimated_cost_lkr"]["typical"] for r in recommendations
                         if r.get("estimated_cost_lkr"))

        planned = set(range(len(faults)) if repair_indices is None else repair_indices)
        remaining = [f for i, f in enumerate(faults) if i not in planned]
        value_plan = self._value(self._after_repair(vehicle, remaining), self.condition)
        plan_cost = sum(r["estimated_cost_lkr"]["typical"] for r in recommendations
                        if r["fault_index"] in planned and r.get("estimated_cost_lkr"))
        return {
            "vehicle_id": vehicle.get("vehicle_id"),
            "baseline_market_value_lkr": round(baseline_value),
            "condition_adjusted_value_lkr": round(condition_value),
            "condition_adjustment_lkr": round(condition_value - baseline_value),
            "recommendations": recommendations,
            "scenario_all_repaired": {
                "estimated_value_lkr": round(value_all_fixed),
                "potential_value_change_lkr": round(value_all_fixed - condition_value),
                "total_typical_repair_cost_lkr": total_cost,
            },
            "scenario_selected": {
                "repair_indices": sorted(planned),
                "estimated_value_lkr": round(value_plan),
                "potential_value_change_lkr": round(value_plan - condition_value),
                "total_typical_repair_cost_lkr": plan_cost,
                "net_after_cost_lkr": round(value_plan - condition_value - plan_cost),
            },
            "note": "Values are model estimates, not guaranteed selling prices.",
        }

    @staticmethod
    def _required_fields():
        num, cat = data.feature_sets()["condition_aware_C1_C2_C3"]
        return num + cat


def demo(vehicle_id=None):
    master = data.load_master()
    events = data.load_fault_events()
    if vehicle_id is None:
        vehicle_id = master.loc[master.fault_count >= 2, "vehicle_id"].iloc[0]
    vehicle = master.loc[master.vehicle_id == vehicle_id].iloc[0].to_dict()
    faults = events.loc[events.vehicle_id == vehicle_id, ["fault_code", "severity"]].to_dict("records")
    result = Component4Engine().assess(vehicle, faults)
    print(json.dumps(result, indent=2, default=str))
    print(f"\nActual listing price in dataset: {vehicle['listing_price_lkr']:,} LKR")


if __name__ == "__main__":
    demo(sys.argv[1] if len(sys.argv) > 1 else None)
