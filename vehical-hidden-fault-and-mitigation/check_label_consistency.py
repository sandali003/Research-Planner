
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

CSV_FILE = (
    BASE_DIR
    / "cleaned_data"
    / "AutoSense_Toyota_Battery_Voltage_Deduplicated.csv"
)

df = pd.read_csv(CSV_FILE)

sensor_columns = [
    "engine_rpm",
    "battery_voltage_v",
    "engine_temp_c",
    "engine_load_pct",
]

print("===== SENSOR PATTERN / LABEL CHECK =====")

# Count different labels for identical sensor readings
label_counts = (
    df.groupby(sensor_columns)["fault_label"]
    .nunique()
)

ambiguous_patterns = label_counts[label_counts > 1]

print("Unique sensor patterns:", len(label_counts))
print(
    "Sensor patterns associated with multiple labels:",
    len(ambiguous_patterns)
)

if len(ambiguous_patterns) > 0:
    print("\nExample ambiguous patterns:")

    examples = ambiguous_patterns.head(10).index
    example_df = df.set_index(sensor_columns).loc[examples].reset_index()

    print(
        example_df[
            sensor_columns + ["fault_label", "vehicle_model"]
        ].to_string(index=False)
    )
else:
    print("No identical sensor patterns have conflicting labels.")

print("\n===== CHECK COMPLETE =====")
print("No files were modified.")
