
import joblib

from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report

from data_prep import load_inspections, INSPECTION_FILE, INSPECTION_4K_FILE, CONDITION_ORDER

# inspection_score is NOT used as an input: overall_condition is just
# inspection_score cut into ranges (20-39 Critical, 40-59 Poor, 60-79 Fair,
# 80-100 Good), so using it would give ~100% accuracy without learning anything.
features = ["component", "component_state", "vehicle_model"]
target = "overall_condition"


def make_model():
    preprocessor = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore"), features)
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
        )),
    ])


def evaluate(path):
    # 1. Load dataset (exact duplicate rows removed)
    df = load_inspections(path)
    X, y, groups = df[features], df[target], df["vehicle_id"]

    # 2. Vehicle-level cross-validation: a vehicle is never in train and test together
    cv = GroupKFold(n_splits=5)
    pred = cross_val_predict(make_model(), X, y, groups=groups, cv=cv)
    base = cross_val_predict(DummyClassifier(strategy="most_frequent"), X, y, groups=groups, cv=cv)

    print(f"\n=== {path} ({len(df)} unique records, {groups.nunique()} vehicles)")
    print("  Model            accuracy:", round(accuracy_score(y, pred), 3),
          " macro F1:", round(f1_score(y, pred, average="macro"), 3))
    print("  Majority-class   accuracy:", round(accuracy_score(y, base), 3),
          " macro F1:", round(f1_score(y, base, average="macro"), 3))
    return df, pred


# 3. The 7000-record dataset is the main one
df, pred = evaluate(INSPECTION_FILE)
print("\nClassification report (7000-record dataset):")
print(classification_report(df[target], pred, labels=CONDITION_ORDER, zero_division=0))

# 4. The 4000-record dataset is checked too, but its component condition has no
# relationship with overall condition, so it is not used for the final model.
evaluate(INSPECTION_4K_FILE)

# 5. Train final model on the 7000-record dataset and save
model = make_model()
model.fit(df[features], df[target])
joblib.dump(model, "models/vehicle_condition_model.joblib", compress=3)

print("\nModel saved successfully!")
print("File: models/vehicle_condition_model.joblib")
