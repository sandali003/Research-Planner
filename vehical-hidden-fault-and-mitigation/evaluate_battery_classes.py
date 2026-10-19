
import json
import joblib
import pandas as pd

from sklearn.model_selection import (
    StratifiedGroupKFold, cross_val_predict
)
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    balanced_accuracy_score,
    accuracy_score
)

DATA_PATH = (
    "cleaned_data/"
    "AutoSense_Toyota_Battery_Voltage_Deduplicated.csv"
)
MODEL_PATH = "models/autosense_fault_model.joblib"

df = pd.read_csv(DATA_PATH)

features = [
    "engine_rpm",
    "battery_voltage_v",
    "engine_temp_c",
    "engine_load_pct"
]

X = df[features]
y = df["fault_label"]

# Similar sensor patterns ekama fold ekakata group karanawa
groups = (
    X.astype(str)
    .agg("|".join, axis=1)
)

model = joblib.load(MODEL_PATH)

cv = StratifiedGroupKFold(
    n_splits=5,
    shuffle=True,
    random_state=42
)

predictions = cross_val_predict(
    model,
    X,
    y,
    groups=groups,
    cv=cv,
    method="predict"
)

print("\n=== CLASS-WISE RESULTS ===")
print(classification_report(
    y,
    predictions,
    zero_division=0
))

print("\n=== CONFUSION MATRIX ===")
labels = sorted(y.unique())
print("Label order:", labels)
print(confusion_matrix(
    y,
    predictions,
    labels=labels
))

print("\n=== OVERALL METRICS ===")
print(
    "Accuracy:",
    round(accuracy_score(y, predictions), 4)
)
print(
    "Balanced accuracy:",
    round(
        balanced_accuracy_score(y, predictions),
        4
    )
)
