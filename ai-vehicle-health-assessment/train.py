"""Train a model for each vehicle dataset in ./malindu and save models to ./models."""
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.metrics import accuracy_score, classification_report, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATA = Path(__file__).parent / "malindu"
OUT = Path(__file__).parent / "models"
OUT.mkdir(exist_ok=True)

# name: (file, target, task, columns to drop). Dropped columns are IDs, free text, or
# values derived from the target (would leak the answer).
DATASETS = {
    "inspection": (
        "Toyota_Standardized_Vehicle_Inspection_Synthetic_20000.csv", "health_class", "clf",
        ["vehicle_id", "inspection_date", "inspection_score", "overall_condition"]),
    "external_sensor": (
        "AutoSense_Fabricated_Toyota_External_Sensor_Dataset_10000.csv", "health_class_simulated", "clf",
        ["record_id", "timestamp", "vehicle_id", "dtc_codes_simulated", "health_score_0_100_simulated",
         "condition_group_simulated", "measurement_source", "label_source", "notes"]),
    "battery": (
        "AutoSense_Toyota_Battery_Voltage_8000.csv", "fault_label", "clf", ["vehicle_id"]),
    "petrol_engine": (
        "Toyota_Petrol_Engine_Synthetic_8000.csv", "Target_Score", "reg", []),
    "engine_data": (
        "engine_data_with_vehicle_model.csv", "Engine Condition", "clf", []),
    "engine_fault": (
        "engine_fault_detection_with_vehicle_model.csv", "Engine_Condition", "clf", []),
}


def candidates(task):
    if task == "clf":
        return {"RandomForest": RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=42),
                "HistGradientBoosting": HistGradientBoostingClassifier(random_state=42)}
    return {"RandomForest": RandomForestRegressor(n_estimators=300, n_jobs=-1, random_state=42),
            "HistGradientBoosting": HistGradientBoostingRegressor(random_state=42)}


def run(name, file, target, task, drop):
    df = pd.read_csv(DATA / file).drop(columns=drop).dropna(subset=[target])
    X, y = df.drop(columns=[target]), df[target]
    X = X.loc[:, X.nunique() > 1]
    cat = X.select_dtypes(exclude="number").columns.tolist()
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), cat)], remainder="passthrough")
    strat = y if task == "clf" else None
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=strat)

    best = None
    print(f"\n===== {name}  ({len(df)} rows, target={target}) =====")
    for mname, model in candidates(task).items():
        pipe = Pipeline([("pre", pre), ("model", model)]).fit(Xtr, ytr)
        pred = pipe.predict(Xte)
        if task == "clf":
            score = f1_score(yte, pred, average="macro")
            print(f"{mname}: accuracy={accuracy_score(yte, pred):.4f}  macro-F1={score:.4f}")
        else:
            score = r2_score(yte, pred)
            print(f"{mname}: R2={score:.4f}  MAE={mean_absolute_error(yte, pred):.4f}")
        if best is None or score > best[0]:
            best = (score, mname, pipe, pred)

    score, mname, pipe, pred = best
    print(f"-> best: {mname}")
    if task == "clf":
        print(classification_report(yte, pred, zero_division=0))
    joblib.dump(pipe, OUT / f"{name}.joblib")
    return {"model": mname, "rows": len(df), "target": target, "task": task,
            "score": round(score, 4), "features": X.columns.tolist()}


if __name__ == "__main__":
    summary = {n: run(n, *cfg) for n, cfg in DATASETS.items()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\nSaved models to", OUT)
