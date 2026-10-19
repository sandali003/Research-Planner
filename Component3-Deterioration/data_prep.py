
"""Shared loading and cleaning for every dataset in this project.

All training scripts import from here so that every model sees the
same cleaned data (duplicates removed, labels normalised, numbers parsed).
"""
import pandas as pd

SERVICE_FILES = [
    "final_dataset_kaggle_3000_rows_same_columns.csv",
    "Toyota_Service_Dataset_6000_Synthetic_Records.csv",
]
INSPECTION_FILE = "Toyota_Vehicle_Inspection_Condition_Synthetic_7000.csv"
INSPECTION_4K_FILE = "Toyota_Inspection_Condition_Filled_Synthetic_4000.csv"
ODOMETER_FILE = "Toyota_Vehicle_Mileage_Odometer_Synthetic_7000.csv"
OBD_FILE = "Toyota_Models_OBDII_4000_Records_Member3.csv"
OBD_REFERENCE_FILE = "Toyota_Target_Models_24000_Records.csv"

# Same meaning, different spelling -> one label
PROBLEM_SYNONYMS = {
    "Engine misfiring": "Engine misfire",
    "Brakes making noise": "Brake noise",
}
SOLUTION_SYNONYMS = {
    "Transmission fluid replacement": "Transmission fluid change",
    "Exhaust system repair": "Exhaust repair",
    "Tire alignment": "Wheel alignment",
}

CONDITION_ORDER = ["Critical", "Poor", "Fair", "Good"]


def build_service_text(service_history, common_problem):
    return "Service history: " + service_history + " Common problem: " + common_problem


def load_service_data():
    """Kaggle 3000 + synthetic 6000 service records, cleaned."""
    frames = []
    for path in SERVICE_FILES:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        df = df[["SERVICE HISTORY", "COMMON PROBLEM", "SOLUTION USED"]].copy()
        df["source"] = path
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    for col in ["SERVICE HISTORY", "COMMON PROBLEM", "SOLUTION USED"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["SERVICE HISTORY"] = df["SERVICE HISTORY"].str.replace(",", ";")
    df["COMMON PROBLEM"] = df["COMMON PROBLEM"].replace(PROBLEM_SYNONYMS)
    df["SOLUTION USED"] = df["SOLUTION USED"].replace(SOLUTION_SYNONYMS)
    df = df[df["SOLUTION USED"] != ""]

    df["input_text"] = build_service_text(df["SERVICE HISTORY"], df["COMMON PROBLEM"])
    return df.reset_index(drop=True)


def split_component_condition(df):
    parts = df["component_condition"].str.split(":", n=1)
    df["component"] = parts.str[0].str.strip()
    df["component_state"] = parts.str[1].str.strip()
    return df


def load_inspections(path=INSPECTION_FILE):
    """Inspection records with exact duplicate rows removed."""
    df = pd.read_csv(path).drop_duplicates().reset_index(drop=True)
    df = split_component_condition(df)
    if df["inspection_date"].notna().any():
        df["inspection_date"] = pd.to_datetime(df["inspection_date"], format="%m/%d/%Y")
    return df


def load_odometer():
    """Odometer readings with one manufacture year per vehicle.

    The raw file gives the same vehicle different manufacture years on
    different rows, so the most frequent year is used as the true one.
    """
    df = pd.read_csv(ODOMETER_FILE).drop_duplicates().reset_index(drop=True)
    df["reading_date"] = pd.to_datetime(df["reading_date"], format="%m/%d/%Y")
    true_year = df.groupby("vehicle_id")["manufacture_year"].agg(
        lambda s: s.value_counts().sort_index().idxmax()
    )
    df["manufacture_year"] = df["vehicle_id"].map(true_year)
    return df


def build_deterioration_table():
    """One row per inspection with vehicle age and the nearest odometer reading."""
    insp = load_inspections().sort_values("inspection_date")
    odo = load_odometer().sort_values("reading_date")

    df = pd.merge_asof(
        insp,
        odo[["vehicle_id", "reading_date", "odometer_km", "manufacture_year"]],
        left_on="inspection_date",
        right_on="reading_date",
        by="vehicle_id",
        direction="nearest",
    )
    df["age_years"] = (
        df["inspection_date"] - pd.to_datetime(df["manufacture_year"].astype(str) + "-07-01")
    ).dt.days / 365.25
    df["poor_condition"] = (df["inspection_score"] < 60).astype(int)
    return df.dropna(subset=["odometer_km", "age_years"]).reset_index(drop=True)


def _to_number(series):
    """'35,70%' -> 35.7 (the 24k file uses comma decimals and % signs)."""
    return pd.to_numeric(
        series.astype(str).str.replace("%", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )


OBD_FEATURES = ["engine_rpm", "engine_load", "coolant_temp"]


def load_obd_reference():
    """Real OBD-II driving log (one car, 2017) used as the 'normal behaviour' reference.

    The requested_toyota_model column is ignored: every row is the same car,
    so that label carries no information.
    """
    raw = pd.read_csv(OBD_REFERENCE_FILE, low_memory=False)
    df = pd.DataFrame({
        "engine_rpm": _to_number(raw["ENGINE_RPM"]),
        "engine_load": _to_number(raw["ENGINE_LOAD"]),
        "coolant_temp": _to_number(raw["ENGINE_COOLANT_TEMP"]),
        "speed": _to_number(raw["SPEED"]),
        "engine_runtime": raw["ENGINE_RUNTIME"],
    })
    df = df.drop_duplicates().dropna(subset=OBD_FEATURES)
    return df[OBD_FEATURES].reset_index(drop=True)


def load_obd_readings():
    df = pd.read_csv(OBD_FILE).drop_duplicates().reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df
