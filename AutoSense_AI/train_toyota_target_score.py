
import os
import json
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# Dataset eka load karanawa
DATA_PATH = "raw_data/Toyota_Petrol_Engine_Synthetic_8000.csv"

df = pd.read_csv(DATA_PATH)

print("Dataset loaded successfully!")
print("Dataset shape:", df.shape)

# Target column eka
target = "Target_Score"

# Target leakage risk eka adu karanna
# me columns model input walata ganneth naha
excluded_columns = [
    target,
    "Combustion_Mode",
    "Gross_Indicated_Thermal_Efficiency"
]

X = df.drop(columns=excluded_columns)
y = df[target]

# Numeric saha categorical columns
categorical_features = ["vehicle_model"]

numeric_features = [
    col for col in X.columns
    if col not in categorical_features
]

# Missing values handle karanawa
# vehicle_model categorical feature ekak widihata encode karanawa
preprocessor = ColumnTransformer([
    (
        "numeric",
        SimpleImputer(strategy="median"),
        numeric_features
    ),
    (
        "categorical",
        Pipeline([
            (
                "imputer",
                SimpleImputer(strategy="most_frequent")
            ),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore")
            )
        ]),
        categorical_features
    )
])

# Regression model eka
model = Pipeline([
    ("preprocessor", preprocessor),
    (
        "regressor",
        GradientBoostingRegressor(random_state=42)
    )
])

# Training saha testing data bedanawa
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

print("Training rows:", len(X_train))
print("Testing rows:", len(X_test))

# Model eka train karanawa
model.fit(X_train, y_train)

# Test data walin predictions
predictions = model.predict(X_test)

# Performance evaluation
r2 = r2_score(y_test, predictions)
mae = mean_absolute_error(y_test, predictions)
rmse = mean_squared_error(
    y_test, predictions
) ** 0.5

print("\n===== MODEL RESULTS =====")
print(f"R2 Score: {r2:.4f}")
print(f"MAE: {mae:.4f}")
print(f"RMSE: {rmse:.4f}")

# Evaluation eken passe full dataset ekata train karanawa
model.fit(X, y)

# Output folders/files
os.makedirs("models", exist_ok=True)

joblib.dump(
    model,
    "models/toyota_target_score_model.joblib"
)

metadata = {
    "task": "Target_Score regression",
    "dataset_rows": int(len(df)),
    "features": list(X.columns),
    "excluded_columns": excluded_columns,
    "r2": float(r2),
    "mae": float(mae),
    "rmse": float(rmse),
    "note": (
        "Synthetic dataset. Target_Score is not a "
        "direct engine fault label."
    )
}

with open(
    "models/toyota_target_score_metadata.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(metadata, file, indent=4)

print("\nTraining completed!")
print("Model saved in models folder.")
print("Metadata saved in models folder.")
