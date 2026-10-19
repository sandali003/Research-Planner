
import joblib
import pandas as pd

from train_deterioration_model import deterioration_status

bundle = joblib.load("deterioration_model.joblib")


def assess_vehicle(vehicle_model, age_years, odometer_km, component, component_state):
    row = pd.DataFrame([{
        "vehicle_model": vehicle_model,
        "age_years": age_years,
        "odometer_km": odometer_km,
        "component": component,
        "component_state": component_state,
    }])
    expected = float(bundle["expected_model"].predict(row[bundle["baseline_features"]])[0])
    observed = float(bundle["observed_model"].predict(row[bundle["evidence_features"]])[0])
    deviation = observed - expected
    status = str(deterioration_status(pd.Series([deviation]), bundle["threshold"])[0])

    reasons = [f"{component} reported as {component_state}"]
    km_per_year = odometer_km / max(age_years, 1)
    if km_per_year > 1.3 * bundle["typical_km_per_year"]:
        reasons.append(f"high usage: {km_per_year:,.0f} km/year")

    return {
        "expected_condition": round(expected, 1),
        "observed_condition": round(observed, 1),
        "deterioration_deviation": round(deviation, 1),
        "deterioration_status": status,
        "reasons": reasons,
    }


if __name__ == "__main__":
    result = assess_vehicle(
        vehicle_model=input("Vehicle model (Axio/Allion/Corolla/Premio/Vitz/Yaris): "),
        age_years=float(input("Vehicle age (years): ")),
        odometer_km=float(input("Odometer (km): ")),
        component=input("Component (e.g. Brakes, Engine, Battery): "),
        component_state=input("Component state (Good/Fair/Poor/Critical): "),
    )
    for key, value in result.items():
        print(f"{key}: {value}")
