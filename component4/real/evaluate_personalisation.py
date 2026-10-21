"""Does the personalised plan earn the owner more than generic advice?

Test cars: real Sri Lankan Toyota ads (Axio, Premio, Allion, Vitz, Corolla, Yaris),
each given the defects of a real UK MOT Toyota of the same age (Component 3 data),
so the defect combinations are realistic. The comparable-car grade distribution is
the MOT distribution for that age and mileage band (what Component 3 returns).

Owner situations: budgets, private buyer or dealer, sale tomorrow or in a week.

Strategies, all within the same budget and time limit:
  Do nothing           sell as is
  Generic: schedule    fix worn components in a fixed maintenance order
                       (brakes, tyres, suspension, steering, exhaust) while the budget lasts
  Generic: worst first fix the worst component first while the budget lasts
  Personalised         value_uplift.py

To avoid grading the engine with its own model, plans are made with typical costs
and the model's value estimates, but scored with
  - a random actual cost per repair (triangular between the min and max quote), and
  - an uncertain value effect: condition effect scaled by U(0.6, 1.2) (transfer from
    US auction data) and a percentile error of N(0, 0.05) per car.
Metrics: mean net gain (value gain - cost), share of cars where the owner loses
money, return per rupee, money spent.

Run (from component4):  .venv\\Scripts\\python real\\evaluate_personalisation.py
"""

from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

REAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REAL_DIR))

from ikman_data import TARGET_MODELS, load  # noqa: E402
from value_uplift import BUYER_FACTOR, ValueUpliftEngine  # noqa: E402

MOT_FILE = REAL_DIR.parent.parent / "Component3-Deterioration" / "external_data" / "mot_toyota_2023.csv"
REPORT_FILE = REAL_DIR / "reports" / "personalisation_results.md"

SEED = 42
N_CARS = 300
COMPONENTS = ["brakes", "tyres", "suspension", "steering", "emissions_leaks"]   # schedule order
LABEL = {"brakes": "Brakes", "tyres": "Tyres", "suspension": "Suspension", "steering": "Steering",
         "emissions_leaks": "Exhaust_System"}
OVERALL = {5: "Good", 4: "Wear", 3: "Minor", 2: "Major", 1: "Dangerous"}
SCENARIOS = [
    {"budget_lkr": 40_000, "buyer": "private", "sell_within_days": 7},
    {"budget_lkr": 100_000, "buyer": "private", "sell_within_days": 7},
    {"budget_lkr": 250_000, "buyer": "private", "sell_within_days": 7},
    {"budget_lkr": 100_000, "buyer": "dealer", "sell_within_days": 7},
    {"budget_lkr": 250_000, "buyer": "dealer", "sell_within_days": 7},
    {"budget_lkr": 100_000, "buyer": "private", "sell_within_days": 1},
]
AGE_BINS = [0, 3, 5, 7, 9, 11, 13, 15, 18, 22, 45]
KM_BINS = [0, 50_000, 100_000, 150_000, 200_000, 1_000_000]


def mot_grades():
    cols = ["age_years", "odometer_km", "n_dangerous", "n_failures", "n_minor", "n_advisories"]
    cols += [f"{k}_{c}" for c in COMPONENTS for k in ("fail", "minor", "adv")]
    m = pd.read_csv(MOT_FILE, usecols=cols).dropna()
    m["grade"] = np.select([m.n_dangerous > 0, m.n_failures > 0, m.n_minor > 0, m.n_advisories > 0], [1, 2, 3, 4], 5)
    for c in COMPONENTS:
        m[f"g_{c}"] = np.select([m[f"fail_{c}"] > 0, m[f"minor_{c}"] > 0, m[f"adv_{c}"] > 0], [1, 2, 3], 4)
    m["age_bin"] = pd.cut(m.age_years, AGE_BINS)
    m["km_bin"] = pd.cut(m.odometer_km, KM_BINS)
    dist = (m.groupby(["age_bin", "km_bin"], observed=True)["grade"].value_counts(normalize=True)
            .unstack(fill_value=0.0))
    return m, dist


def test_cars(rng):
    ads = load()
    ads = ads[ads.model.isin(TARGET_MODELS) & ads.age_years.between(1, 30)]
    return ads.sample(N_CARS, random_state=SEED).reset_index(drop=True)


def contextual_for(car, m, dist, rng):
    """A Component 3 style result: defects of a real MOT car of similar age, MOT grade distribution."""
    near = m[(m.age_years - car.age_years).abs() <= 1]
    donor = near.iloc[rng.integers(len(near))]
    age_bin = pd.cut([car.age_years], AGE_BINS)[0]
    km_bin = pd.cut([car.mileage_km], KM_BINS)[0]
    try:
        row = dist.loc[(age_bin, km_bin)]
    except KeyError:
        row = dist.xs(age_bin, level=0).mean()
    return {
        "overall": {"grade_distribution": {OVERALL[k]: float(row.get(k, 0.0)) for k in OVERALL}},
        "components": [{"component": LABEL[c], "mot_group": c, "observed_grade": int(donor[f"g_{c}"])}
                       for c in COMPONENTS],
    }


class Outcome:
    """Scores a set of repairs with uncertain real costs and value effects (not the engine's own estimates)."""

    def __init__(self, engine, vehicle, contextual, rng):
        self.e, self.v, self.ctx = engine, vehicle, contextual
        self.scale = rng.uniform(0.6, 1.2)
        self.noise = rng.normal(0, 0.05)
        self.costs = {i: rng.triangular(r.min_lkr, r.typical_lkr, r.max_lkr) for i, r in engine.costs.iterrows()}
        self.grades = {c["mot_group"]: c["observed_grade"] for c in contextual["components"]}
        age = float(vehicle["age_years"])
        self.base = engine.market_value(vehicle)
        self.grid, self.curve = engine._effect_curve(vehicle)
        self.ref = np.interp(engine.condition_at(0.5, age), self.grid, self.curve)
        self.age = age

    def value(self, repaired):
        g = {k: (4 if k in repaired else v) for k, v in self.grades.items()}
        p = self.e.overall_percentile(self.ctx["overall"]["grade_distribution"], self.e.overall_grade(g))
        cond = self.e.condition_at(float(np.clip(p + self.noise, 0, 1)), self.age)
        return self.base * float(np.exp(self.scale * (np.interp(cond, self.grid, self.curve) - self.ref)))

    def net(self, repaired, buyer):
        gain = (self.value(set(repaired)) - self.value(set())) * BUYER_FACTOR[buyer]
        cost = sum(self.costs[r] for r in repaired)
        return gain - cost, gain, cost


def generic(order, grades, costs, budget, days, lead):
    plan, spent = [], 0
    for c in order:
        if grades[c] < 4 and lead[c] <= days and spent + costs[c] <= budget:
            plan.append(c)
            spent += costs[c]
    return plan


def main():
    started = time.perf_counter()
    rng = np.random.default_rng(SEED)
    engine = ValueUpliftEngine()
    m, dist = mot_grades()
    cars = test_cars(rng)
    typical = engine.costs["typical_lkr"].to_dict()
    lead = engine.costs["lead_days"].to_dict()

    rows, plans_per_car = [], []
    for i, car in cars.iterrows():
        vehicle = {"model": car.model, "age_years": float(car.age_years), "mileage_km": float(car.mileage_km),
                   "engine_cc": None if pd.isna(car.engine_cc) else float(car.engine_cc),
                   "fuel_type": str(car.fuel_type).lower()}
        ctx = contextual_for(car, m, dist, rng)
        grades = {c["mot_group"]: c["observed_grade"] for c in ctx["components"]}
        if min(grades.values()) == 4:
            rows.append({"car": i, "has_defects": False})
            continue
        outcome = Outcome(engine, vehicle, ctx, rng)
        worst_order = sorted(COMPONENTS, key=lambda c: (grades[c], COMPONENTS.index(c)))
        car_plans = set()
        for s_i, s in enumerate(SCENARIOS):
            strategies = {
                "Do nothing": [],
                "Generic: schedule": generic(COMPONENTS, grades, typical, s["budget_lkr"], s["sell_within_days"], lead),
                "Generic: worst first": generic(worst_order, grades, typical, s["budget_lkr"], s["sell_within_days"], lead),
                "Personalised": [a["id"] for a in engine.recommend(vehicle, ctx, budget_lkr=s["budget_lkr"],
                                                                     sell_within_days=s["sell_within_days"],
                                                                     buyer=s["buyer"])["plan"]],
            }
            car_plans.add(tuple(sorted(strategies["Personalised"])))
            for name, plan in strategies.items():
                net, gain, cost = outcome.net(plan, s["buyer"])
                rows.append({"car": i, "has_defects": True, "scenario": s_i, "strategy": name, "net": net,
                             "gain": gain, "cost": cost, "repairs": len(plan), **s})
        plans_per_car.append(len(car_plans))
        if i % 50 == 0:
            print(f"  {i}/{len(cars)} cars", flush=True)

    df = pd.DataFrame(rows)
    defect_share = df.drop_duplicates("car")["has_defects"].mean()
    df = df[df.has_defects]

    def summary(g):
        spent = g.cost.sum()
        return pd.Series({"Mean net gain LKR": g.net.mean(), "Mean value gain LKR": g.gain.mean(),
                          "Mean cost LKR": g.cost.mean(), "Owner loses money %": (g.net < 0).mean() * 100,
                          "Value per LKR spent": g.gain.sum() / spent if spent else np.nan,
                          "Mean repairs": g.repairs.mean()})

    order = ["Do nothing", "Generic: schedule", "Generic: worst first", "Personalised"]
    overall = df.groupby("strategy").apply(summary).loc[order]
    by_scenario = df.pivot_table(index="scenario", columns="strategy", values="net", aggfunc="mean")[order]
    by_scenario.index = [f"budget {s['budget_lkr']:,} · {s['buyer']} · {s['sell_within_days']} day(s)" for s in SCENARIOS]

    # Paired comparison: personalised minus the better generic plan, per car and situation
    piv = df.pivot_table(index=["car", "scenario"], columns="strategy", values="net")
    diff = piv["Personalised"] - piv[["Generic: schedule", "Generic: worst first"]].max(axis=1)
    boot = [rng.choice(diff.values, len(diff)).mean() for _ in range(2000)]
    lo, hi = np.percentile(boot, [2.5, 97.5])

    def fmt(df_):
        out = df_.copy()
        for c in out.columns:
            out[c] = out[c].map(lambda v: f"{v:,.0f}" if abs(v) >= 100 else f"{v:.2f}")
        return out

    def md(df_):
        cols = [""] + list(df_.columns)
        lines = ["| " + " | ".join(cols) + " |", "|---" * len(cols) + "|"]
        lines += ["| " + " | ".join([str(i)] + list(r)) + " |" for i, r in zip(df_.index, df_.values)]
        return "\n".join(lines)

    report = [
        "# Personalised value-uplift vs generic advice (Component 4 evaluation)", "",
        f"{N_CARS} real Sri Lankan Toyota ads ({', '.join(TARGET_MODELS)}), each with the defects of a real UK MOT "
        f"Toyota of the same age; {defect_share * 100:.0f}% have at least one defect and are scored. "
        f"{len(SCENARIOS)} owner situations each. Plans use typical costs and the model's estimates; outcomes use a "
        "random actual cost (min-max quote) and an uncertain value effect (x U(0.6, 1.2), percentile error N(0, 0.05)).",
        "", "## All situations", "", md(fmt(overall)), "",
        "## Mean net gain (LKR) by owner situation", "", md(fmt(by_scenario)), "",
        "## Personalised minus the better generic plan (paired, per car and situation)", "",
        f"Mean {diff.mean():+,.0f} LKR (bootstrap 95% CI {lo:+,.0f} to {hi:+,.0f}); personalised is better in "
        f"{(diff > 0).mean() * 100:.0f}%, equal in {(diff.abs() < 1).mean() * 100:.0f}%, worse in {(diff < -1).mean() * 100:.0f}% "
        "(worse only where actual costs or effects differ from the estimates).", "",
        "## Is the plan personalised?", "",
        f"Different plans for the same car across the {len(SCENARIOS)} owner situations: mean "
        f"{np.mean(plans_per_car):.1f}; {np.mean(np.array(plans_per_car) > 1) * 100:.0f}% of cars get more than one plan.", "",
        "Repair costs are placeholder estimates; the value effect comes from US auction data (model 2) applied to "
        "Sri Lankan market values (model 1).", "",
    ]
    REPORT_FILE.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Done in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
