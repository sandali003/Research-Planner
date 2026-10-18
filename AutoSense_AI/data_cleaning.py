
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

CSV_FILE = (
    BASE_DIR
    / "raw_data"
    / "AutoSense_Toyota_Battery_Voltage.csv"
)

df = pd.read_csv(CSV_FILE)

print("===== VEHICLE ID TO MODEL MAPPING =====")

mapping = (
    df.groupby("vehicle_id")["vehicle_model"]
    .agg(
        unique_models="nunique",
        model_names=lambda x: ", ".join(sorted(x.unique()))
    )
    .reset_index()
)

print(mapping.to_string(index=False))

print("\n===== RECORD COUNTS PER MODEL =====")
print(df["vehicle_model"].value_counts().to_string())

print("\n===== LABEL COUNTS PER MODEL =====")
print(
    pd.crosstab(
        df["vehicle_model"],
        df["fault_label"]
    ).to_string()
)

print("\n===== INVESTIGATION COMPLETE =====")
print("Original dataset has not been changed.")
