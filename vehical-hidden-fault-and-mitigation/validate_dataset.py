
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

CSV_FILE = (
    BASE_DIR
    / "raw_data"
    / "AutoSense_Toyota_Battery_Voltage_Deduplicated.csv"
)

df = pd.read_csv(CSV_FILE)

print("===== DATASET VALIDATION =====")

# 1. Check expected columns
expected_columns = [
    "vehicle_id",
    "engine_rpm",
    "battery_voltage_v",
    "engine_temp_c",
    "engine_load_pct",
    "fault_label",
    "vehicle_model",
]

print("\n--- Columns ---")
print("Missing expected columns:",
      sorted(set(expected_columns) - set(df.columns)))
print("Unexpected columns:",
      sorted(set(df.columns) - set(expected_columns)))

# 2. Check missing values and duplicate rows
print("\n--- Integrity ---")
print("Rows:", len(df))
print("Missing values:", int(df.isna().sum().sum()))
print("Remaining exact duplicates:", int(df.duplicated().sum()))

# 3. Check label values
print("\n--- Fault Labels ---")
print(df["fault_label"].value_counts().to_string())

# 4. Check numeric ranges
numeric_columns = [
    "engine_rpm",
    "battery_voltage_v",
    "engine_temp_c",
    "engine_load_pct",
]

print("\n--- Sensor Ranges ---")
print(df[numeric_columns].describe().round(2).to_string())

# 5. Check invalid numeric values
print("\n--- Invalid Numeric Values ---")
print("Non-numeric values:")
print(df[numeric_columns].apply(
    lambda col: pd.to_numeric(col, errors="coerce").isna().sum()
).to_string())

print("\n--- Vehicle ID / Model Check ---")
print("Unique vehicle IDs:", df["vehicle_id"].nunique())
print("Unique vehicle models:", df["vehicle_model"].nunique())
print("Vehicle IDs linked to multiple models:",
      int((df.groupby("vehicle_id")["vehicle_model"].nunique() > 1).sum()))

print("\nValidation complete. No files were modified.")
