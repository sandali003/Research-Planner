
from pathlib import Path
import pandas as pd

# Project folders
BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR
    / "raw_data"
    / "AutoSense_Toyota_Battery_Voltage.csv"
)

OUTPUT_DIR = BASE_DIR / "cleaned_data"
OUTPUT_FILE = (
    OUTPUT_DIR
    / "AutoSense_Toyota_Battery_Voltage_Deduplicated.csv"
)

# Check input file
if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Dataset not found: {INPUT_FILE}"
    )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load original dataset
df = pd.read_csv(INPUT_FILE)

print("===== ORIGINAL DATASET =====")
print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")
print(f"Missing values: {df.isna().sum().sum()}")

# Check duplicate rows
duplicate_count = int(df.duplicated().sum())

print(f"Exact duplicate rows: {duplicate_count}")

# Remove exact duplicate rows only
cleaned_df = df.drop_duplicates().copy()

# Save a separate candidate dataset
cleaned_df.to_csv(OUTPUT_FILE, index=False)

print("\n===== CANDIDATE DATASET =====")
print(f"Rows after deduplication: {len(cleaned_df)}")
print(f"Rows removed: {len(df) - len(cleaned_df)}")
print(f"Missing values remaining: {cleaned_df.isna().sum().sum()}")
print(f"\nSaved to: {OUTPUT_FILE}")

print("\n===== FAULT LABEL DISTRIBUTION =====")
print(cleaned_df["fault_label"].value_counts().to_string())

print("\nOriginal dataset remains unchanged.")
