"""Component 4: personalised value-uplift recommendations.

"Which repairs are worth doing before selling this car, and how much could they
add to its price?" For one vehicle the engine combines

  model 1  Sri Lankan market value (ikman.lk ads)            -> base value in LKR
  model 2  verified condition -> price effect (US auctions)  -> % change per condition
  Component 3  where the car's condition sits among comparable cars (grade distribution)
  Component 2  hidden faults and their severity (safety)
  repair_costs.csv  cost and lead time of each repair (placeholder estimates)

and the owner's situation (budget, days until the sale, private buyer or dealer).

Steps
  1. Current condition: Component 3's overall grade -> percentile among comparable
     cars -> the same percentile of the condition score (model 2's Toyota condition
     distribution for this age) -> condition-adjusted value.
  2. Each repair of a Component 3 component sets it to Good; the overall grade is
     the worst remaining component (as in the MOT), which gives a new percentile,
     condition and value. Value gain = new value - current value.
  3. Component 2 faults with High severity are safety repairs: always first,
     whatever their return. Their effect on price is not measured in the data,
     so no value gain is claimed for them.
  4. The plan is the set of repairs with the highest net gain (value gain x buyer
     factor - cost) that fits the budget and the days left before the sale.

Value gains are model estimates with a range, not guaranteed prices. Seller claims
in ads ("service records", "new tyres") showed no price premium in the Sri Lankan
data (train_valuation_sl.py), so only verified condition changes are valued.
"""

from itertools import combinations
import math
from pathlib import Path
import re

import joblib
import numpy as np
import pandas as pd

REAL_DIR = Path(__file__).resolve().parent
MODEL_DIR = REAL_DIR / "models"

OVERALL_GRADES = {5: "Good", 4: "Wear", 3: "Minor", 2: "Major", 1: "Dangerous"}
COMPONENT_GRADES = {4: "Good", 3: "Wear", 2: "Minor", 1: "Major"}
MILES_PER_KM = 1 / 1.609344
PERCENTILE_PROBS = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
UNCERTAINTY = 0.10   # +/- percentile shift used for the value range

# Share of a value gain a buyer pays for. Dealers recondition cars themselves and
# price that in; 0.5 is an assumption to be checked with dealers.
BUYER_FACTOR = {"private": 1.0, "dealer": 0.5}

BODY = {"Vitz": "Hatchback", "Aqua": "Hatchback", "Passo": "Hatchback"}
FUEL = {"petrol": "Petrol", "hybrid": "Hybrid", "diesel": "Diesel"}
AUCTION_BODY = {"Hatchback": "hatchback", "Saloon": "sedan"}


def _band_bounds(label):
    lo, hi = (float(x) for x in re.findall(r"-?\d+\.?\d*", label)[:2])
    return lo, hi


class ValueUpliftEngine:
    def __init__(self):
        self.valuation = joblib.load(MODEL_DIR / "sl_valuation.joblib")
        self.effect = joblib.load(MODEL_DIR / "condition_effect.joblib")
        self.costs = pd.read_csv(REAL_DIR / "repair_costs.csv").set_index("action_id")
        q = self.effect["toyota_condition_quantiles"]
        self.condition_bands = [(*_band_bounds(str(i)), row.values.astype(float)) for i, row in q.iterrows()]

    # ---------------- valuation ----------------
    def market_value(self, v):
        """Sri Lankan asking price for a typical car like this (model 1), LKR."""
        row = {
            "age_years": v["age_years"], "mileage_km": v["mileage_km"], "engine_cc": v.get("engine_cc"),
            "model": v["model"], "fuel_type": FUEL.get(str(v.get("fuel_type", "petrol")).lower(), "Petrol"),
            "transmission": v.get("transmission", "Automatic"), "condition": "Used",
            "body_type": v.get("body_type") or BODY.get(v["model"], "Saloon"),
        }
        for a in self.valuation["attributes"]:
            row[a] = 0   # seller claims carry no measurable premium
        cols = self.valuation["numeric"] + self.valuation["categorical"]
        return float(self.valuation["model"].predict(pd.DataFrame([row])[cols])[0])

    def _condition_quantiles(self, age):
        for lo, hi, values in self.condition_bands:
            if lo < age <= hi:
                return values
        return self.condition_bands[-1][2] if age > self.condition_bands[-1][1] else self.condition_bands[0][2]

    def condition_at(self, percentile, age):
        """Auction condition score (10-49) at this percentile of Toyotas of this age."""
        return float(np.interp(percentile, PERCENTILE_PROBS, self._condition_quantiles(age)))

    def _effect_curve(self, v):
        """log price-to-market ratio by condition 10-49 for this car's age and mileage (model 2)."""
        typical = self.effect["toyota_typical"]
        grid = np.arange(10, 50, dtype=float)
        rows = pd.DataFrame({
            "age_years": v["age_years"], "log_odometer": np.log1p(v["mileage_km"] * MILES_PER_KM),
            "log_mmr": typical["log_mmr"], "condition": grid, "make": "toyota",
            "body": AUCTION_BODY.get(v.get("body_type") or BODY.get(v["model"], "Saloon"), "sedan"),
            "transmission": "automatic",
        })
        return grid, self.effect["model"].predict(rows[self.effect["features"]])

    # ---------------- condition from Component 3 ----------------
    @staticmethod
    def overall_percentile(distribution, grade):
        """Share of comparable cars in a worse overall grade (mid-rank), from Component 3's distribution."""
        probs = {k: distribution.get(name, 0.0) for k, name in OVERALL_GRADES.items()}
        return sum(p for k, p in probs.items() if k < grade) + 0.5 * probs[grade]

    @staticmethod
    def overall_grade(component_grades):
        """Worst component sets the vehicle grade (MOT style): component 4..1 -> overall 5..2."""
        return min(component_grades.values()) + 1 if component_grades else 5

    # ---------------- recommendations ----------------
    def recommend(self, vehicle, contextual, faults=(), budget_lkr=None, sell_within_days=None, buyer="private"):
        """Personalised plan.

        vehicle:    {model, age_years, mileage_km, engine_cc?, fuel_type?, transmission?, body_type?}
        contextual: Component 3 'contextual' result (overall.grade_distribution, components[...])
        faults:     Component 2 issues [{fault, severity}]
        """
        age = float(vehicle["age_years"])
        base = self.market_value(vehicle)
        grid, curve = self._effect_curve(vehicle)
        ref_condition = self.condition_at(0.5, age)      # ad prices reflect a typical car of this age
        ref_effect = np.interp(ref_condition, grid, curve)

        def value(percentile):
            cond = self.condition_at(min(max(percentile, 0.0), 1.0), age)
            return base * float(np.exp(np.interp(cond, grid, curve) - ref_effect)), cond

        distribution = contextual["overall"]["grade_distribution"]
        grades = {c["mot_group"]: int(c["observed_grade"]) for c in contextual["components"]}
        labels = {c["mot_group"]: c["component"] for c in contextual["components"]}

        def state(repaired):
            g = {k: (4 if k in repaired else v) for k, v in grades.items()}
            p = self.overall_percentile(distribution, self.overall_grade(g))
            return p, value(p)

        now_p, (now_value, now_cond) = state(())
        factor = BUYER_FACTOR.get(buyer, 1.0)

        actions = []
        for group, grade in grades.items():
            if grade < 4 and group in self.costs.index:
                actions.append({"id": group, "kind": "value", "component": labels[group],
                                "reason": f"{labels[group].replace('_', ' ')} is in '{COMPONENT_GRADES[grade]}' condition"})
        for f in faults:
            if f["fault"] in self.costs.index:
                actions.append({"id": f["fault"], "kind": "safety" if f.get("severity") == "High" else "fault",
                                "component": f["fault"],
                                "reason": f"Component 2 found {f['fault'].replace('_', ' ').lower()} ({f.get('severity', '?')} severity)"})

        for a in actions:
            c = self.costs.loc[a["id"]]
            a.update(action=c["action"], cost_lkr=int(c["typical_lkr"]), cost_range_lkr=[int(c["min_lkr"]), int(c["max_lkr"])],
                     lead_days=int(c["lead_days"]), cost_source=c["source"])

        def gain_of(repaired):
            p, (val, _) = state(repaired)
            lo = min(value(p + s)[0] - value(now_p + s)[0] for s in (-UNCERTAINTY, UNCERTAINTY))
            hi = max(value(p + s)[0] - value(now_p + s)[0] for s in (-UNCERTAINTY, UNCERTAINTY))
            return val - now_value, min(lo, val - now_value), max(hi, val - now_value)

        # Value of each repair on its own (for the explanation)
        for a in actions:
            if a["kind"] == "value":
                g, lo, hi = gain_of({a["id"]})
            else:
                g = lo = hi = 0.0
            a["value_gain_lkr"] = round(g * factor)
            a["value_gain_range_lkr"] = [round(lo * factor), round(hi * factor)]
            a["net_gain_lkr"] = a["value_gain_lkr"] - a["cost_lkr"]
            a["roi"] = round(a["value_gain_lkr"] / a["cost_lkr"], 2) if a["cost_lkr"] else None

        mandatory = [a for a in actions if a["kind"] == "safety"]
        reliability = [a for a in actions if a["kind"] == "fault"]   # not safety-critical, no price effect measured
        optional = [a for a in actions if a["kind"] == "value"
                    and (sell_within_days is None or a["lead_days"] <= sell_within_days)]
        too_slow = [a for a in actions if a["kind"] == "value" and a not in optional]

        # Best set: repairs interact (only the worst component sets the grade), so every subset is scored
        mandatory_cost = sum(a["cost_lkr"] for a in mandatory)
        best, best_net = (), -np.inf
        for r in range(len(optional) + 1):
            for subset in combinations(optional, r):
                cost = mandatory_cost + sum(a["cost_lkr"] for a in subset)
                if budget_lkr is not None and cost > budget_lkr and subset:
                    continue
                gain = gain_of({a["id"] for a in subset})[0] * factor
                net = gain - sum(a["cost_lkr"] for a in subset)
                if net > best_net + 1e-6:
                    best, best_net = subset, net
        # Repairs interact: one may only pay off together with another, so the whole best set is kept
        plan = mandatory + list(best)
        plan_value_ids = {a["id"] for a in plan if a["kind"] == "value"}
        plan_gain, plan_lo, plan_hi = gain_of(plan_value_ids)

        # Share of the plan's value gain per repair (Shapley values): repairs only pay off
        # together when another component is just as bad, so a repair's gain on its own
        # can be 0 while it is needed in the plan. The shares add up to the plan's gain.
        ids = sorted(plan_value_ids)
        shapley = {i: 0.0 for i in ids}
        n = len(ids)
        for i in ids:
            others = [j for j in ids if j != i]
            for r in range(n):
                for coalition in combinations(others, r):
                    weight = math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
                    shapley[i] += weight * (gain_of(set(coalition) | {i})[0] - gain_of(set(coalition))[0])
        for a in plan:
            if a["kind"] == "value":
                a["gain_if_done_alone_lkr"] = a["value_gain_lkr"]
                a["value_gain_lkr"] = round(shapley[a["id"]] * factor)
                a["net_gain_lkr"] = a["value_gain_lkr"] - a["cost_lkr"]
                a["roi"] = round(a["value_gain_lkr"] / a["cost_lkr"], 2) if a["cost_lkr"] else None
        after_p, (after_value, after_cond) = state(plan_value_ids)
        plan_cost = sum(a["cost_lkr"] for a in plan)

        skipped = [{**a, "why_not": "costs more than it adds to the price" if a["net_gain_lkr"] <= 0
                    else "does not fit the budget with the better repairs"}
                   for a in optional if a not in plan]
        skipped += [{**a, "why_not": f"needs {a['lead_days']} days, the sale is in {sell_within_days}"} for a in too_slow]

        notes = []
        if budget_lkr is not None and mandatory_cost > budget_lkr:
            notes.append(f"Safety repairs (LKR {mandatory_cost:,}) exceed the budget; they come first regardless.")
        if mandatory or reliability:
            notes.append("Fault repairs from Component 2 are recommended for safety and reliability; "
                         "their effect on price is not measured, so no value gain is claimed.")
        if now_p > 0.5:
            notes.append("This car is in better condition than a typical one of its age. Sharing the AutoSense "
                         "verified report lets buyers see that; seller claims alone showed no price premium.")
        notes.append("Repair costs are placeholder estimates until garage quotes are added.")

        return {
            "market_value_lkr": round(base),
            "condition": {"percentile": round(now_p, 3), "condition_score": round(now_cond, 1),
                          "typical_condition_score": round(ref_condition, 1)},
            "current_value_lkr": round(now_value),
            "plan": [{k: a.get(k) for k in ("id", "kind", "component", "action", "reason", "cost_lkr", "cost_range_lkr",
                                             "lead_days", "value_gain_lkr", "gain_if_done_alone_lkr", "net_gain_lkr", "roi")}
                     for a in sorted(plan, key=lambda a: (a["kind"] != "safety", -a["net_gain_lkr"]))],
            "plan_summary": {
                "cost_lkr": plan_cost,
                "value_gain_lkr": round(plan_gain * factor),
                "value_gain_range_lkr": [round(plan_lo * factor), round(plan_hi * factor)],
                "net_gain_lkr": round(plan_gain * factor - plan_cost),
                "value_after_lkr": round(now_value + plan_gain * factor),
                "condition_score_after": round(after_cond, 1),
                "percentile_after": round(after_p, 3),
            },
            "not_recommended": [{k: a[k] for k in ("id", "component", "action", "cost_lkr", "value_gain_lkr",
                                                   "net_gain_lkr", "why_not")} for a in skipped],
            "reliability_repairs": [{k: a[k] for k in ("id", "component", "action", "reason", "cost_lkr")}
                                    for a in reliability],
            "inputs": {"budget_lkr": budget_lkr, "sell_within_days": sell_within_days, "buyer": buyer,
                       "buyer_factor": factor},
            "notes": notes,
        }


if __name__ == "__main__":
    import json
    engine = ValueUpliftEngine()
    vehicle = {"model": "Axio", "age_years": 9, "mileage_km": 120000, "engine_cc": 1500, "fuel_type": "petrol"}
    contextual = {   # shape of a Component 3 'contextual' result
        "overall": {"grade_distribution": {"Dangerous": 0.06, "Major": 0.2, "Minor": 0.05, "Wear": 0.27, "Good": 0.42}},
        "components": [
            {"component": "Brakes", "mot_group": "brakes", "observed_grade": 1},
            {"component": "Suspension", "mot_group": "suspension", "observed_grade": 3},
            {"component": "Tyres", "mot_group": "tyres", "observed_grade": 2},
        ],
    }
    faults = [{"fault": "Charging_System_Warning", "severity": "High"}]
    for budget in (None, 60000):
        print(f"\n===== budget {budget} =====")
        print(json.dumps(engine.recommend(vehicle, contextual, faults, budget_lkr=budget), indent=1)[:2500])
