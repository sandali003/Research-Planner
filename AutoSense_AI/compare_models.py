
from pathlib import Path

import pandas as pd

from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, classification_report
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

X = df[features]
y = df["fault_label"]

# Keep identical sensor patterns in the same fold.
groups = pd.util.hash_pandas_object(X, index=False)

cv = StratifiedGroupKFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

models = {
    "Random Forest": RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    ),
    "Extra Trees": ExtraTreesClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    ),
}

for name, classifier in models.items():
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("classifier", classifier),
    ])

    predictions = cross_val_predict(
        model,
        X,
        y,
        cv=cv,
        groups=groups,
        method="predict",
        n_jobs=1,
    )

    print(f"\n===== {name} =====")
    print("Accuracy:", round(accuracy_score(y, predictions), 4))
    print(
        "Macro F1:",
        round(f1_score(y, predictions, average="macro"), 4),
    )

    print("\nClass-wise report:")
    print(classification_report(y, predictions, zero_division=0))

print("\nModel comparison complete.")
