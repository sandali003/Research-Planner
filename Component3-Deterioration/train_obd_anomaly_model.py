
"""OBD-II anomaly model (unsupervised).

Neither OBD dataset has a condition label, so a supervised model cannot be
trained or evaluated. Instead an Isolation Forest learns normal engine
behaviour from the real 24000-record OBD log and then scores each reading in
the 4000-record dataset. The share of unusual readings per vehicle can later
be used as extra "observed condition" evidence once OBD vehicle IDs match
the inspection vehicle IDs.
"""
import os
import joblib

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

from data_prep import load_obd_reference, load_obd_readings, OBD_FEATURES

# 1. Load normal-behaviour reference data (duplicates removed, numbers parsed)
reference = load_obd_reference()
print("Reference OBD readings:", len(reference))

# 2. Train Isolation Forest
model = Pipeline([
    ("scale", StandardScaler()),
    ("model", IsolationForest(n_estimators=300, contamination=0.02, random_state=42)),
])
model.fit(reference[OBD_FEATURES])

# 3. Score the vehicle OBD readings
obd = load_obd_readings()
obd["anomaly"] = model.predict(obd[OBD_FEATURES]) == -1
obd["anomaly_score"] = -model.score_samples(obd[OBD_FEATURES])

summary = obd.groupby(["vehicle_id", "vehicle_model"]).agg(
    readings=("anomaly", "size"),
    anomaly_rate=("anomaly", "mean"),
    mean_coolant_temp=("coolant_temp", "mean"),
    mean_engine_load=("engine_load", "mean"),
).reset_index().sort_values("anomaly_rate", ascending=False)

print("Vehicle OBD readings scored:", len(obd), "from", obd["vehicle_id"].nunique(), "vehicles")
print("Overall anomaly rate:", round(obd["anomaly"].mean(), 3))
print("\nVehicles with the most unusual readings:")
print(summary.head(5).round(3).to_string(index=False))

# 4. Save
os.makedirs("reports", exist_ok=True)
summary.round(4).to_csv("reports/obd_vehicle_anomaly.csv", index=False)
joblib.dump({"model": model, "features": OBD_FEATURES}, "models/obd_anomaly_model.joblib", compress=3)

print("\nModel saved: models/obd_anomaly_model.joblib")
print("Per-vehicle summary: reports/obd_vehicle_anomaly.csv")
