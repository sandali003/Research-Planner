"""Data loading and feature preparation shared by training and inference."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "Raw Data" / "sandali" / "New folder"

SEVERITY_LEVEL = {"None": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}
LEVEL_SEVERITY = {v: k for k, v in SEVERITY_LEVEL.items()}
PRIORITY_LEVEL = {"Low": 1, "Medium": 2, "High": 3}

# Market-only features (the proposal's baseline, Section 3.3).
MARKET_NUMERIC = ["vehicle_age", "mileage_km", "engine_capacity_cc"]
MARKET_CATEGORICAL = ["vehicle_model", "fuel_type", "transmission"]

# AutoSense condition outputs, grouped by the component that produces them.
C1_FEATURES = ["health_score"]
C2_FEATURES = ["fault_count", "severity_level"]
C3_NUMERIC = ["deterioration_deviation"]
C3_CATEGORICAL = ["deterioration_class"]

TARGET = "listing_price_lkr"


def _read(name):
    return pd.read_excel(DATA_DIR / name)


def load_master():
    df = _read("01_vehicle_master_with_condition.csv.xlsx")
    df["severity"] = df["severity"].fillna("None")
    df["severity_level"] = df["severity"].map(SEVERITY_LEVEL)
    return df


def load_fault_events():
    return _read("02_vehicle_fault_events.csv.xlsx")


def load_rules():
    return _read("03_fault_rule_table.csv.xlsx")


def load_cost_lookup():
    return _read("04_repair_cost_lookup.csv.xlsx")


def load_cost_records():
    return _read("05_repair_cost_records.csv.xlsx")


def feature_sets():
    """Feature groups for the baseline, each single-component ablation, and the full model."""
    base_num, base_cat = MARKET_NUMERIC, MARKET_CATEGORICAL
    return {
        "baseline_market_only": (base_num, base_cat),
        "market_plus_C1": (base_num + C1_FEATURES, base_cat),
        "market_plus_C2": (base_num + C2_FEATURES, base_cat),
        "market_plus_C3": (base_num + C3_NUMERIC, base_cat + C3_CATEGORICAL),
        "condition_aware_C1_C2_C3": (
            base_num + C1_FEATURES + C2_FEATURES + C3_NUMERIC,
            base_cat + C3_CATEGORICAL,
        ),
    }
