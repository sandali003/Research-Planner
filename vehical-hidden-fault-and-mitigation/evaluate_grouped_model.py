
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = (
    BASE_DIR
    / "cleaned_data"
    / "AutoSense_Toyota_Battery_Voltage_Deduplicated.csv"
)

df = pd.read_csv(DATA_FILE)

features = [
    "engine_rpm",
    "battery_voltage_v",
    "engine_temp_c",
    "engine_load_pct",
]
target = "fault_label"

X = df[features]
y = df[target]

# Give identical sensor patterns the same group ID.
groups = pd.util.hash_pandas_object(X, index=False)

# Confirm that each sensor pattern has only one label.
pattern_labels = df.groupby(features)[target].nunique()

if (pattern_labels > 1).any():
    raise ValueError(
        "Some identical sensor patterns have conflicting labels. "
        "Investigate these before evaluation."
    )

cv = StratifiedGroupKFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

model = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("classifier", RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        class_weight="balanced",
    )),
])

# Each sensor pattern is held out as a group in its test fold.
predictions = cross_val_predict(
    model,
    X,
    y,
    cv=cv,
    groups=groups,
    method="predict",
    n_jobs=-1,
)

print("===== GROUPED CROSS-VALIDATION =====")
print("Rows:", len(df))
print("Unique sensor patterns:", df[features].drop_duplicates().shape[0])
print("Folds: 5")
print("Accuracy:", round(accuracy_score(y, predictions), 4))
print(
    "Macro F1:",
    round(f1_score(y, predictions, average="macro"), 4),
)

print("\n===== CLASSIFICATION REPORT =====")
print(classification_report(y, predictions, zero_division=0))

print("===== CONFUSION MATRIX =====")
labels = sorted(y.unique())
print("Label order:", labels)
print(confusion_matrix(y, predictions, labels=labels))

print("\nGrouped evaluation complete.")
print("No dataset files were modified.")
