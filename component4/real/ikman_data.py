"""Sri Lankan used-car ads (ikman.lk dataset, data_real/vehicles.csv) prepared for valuation.

One row per Toyota car ad: model, age, mileage, engine, fuel, transmission,
condition (Used / Reconditioned), body type, asking price (LKR) and value
attributes found in the ad text (single owner, service records, new tyres ...).

Cleaning
  - cars of brand Toyota, used or reconditioned (brand-new cars are a different market)
  - prices 300,000 - 100,000,000 LKR, mileage up to 600,000 km, age 0 - 45 years
  - the same car re-posted by the same seller (same model, year, mileage, price) is kept once
  - models with fewer than MIN_MODEL_ADS ads are grouped as "Other"
Prices are asking prices, not sale prices.
"""

import ast
from pathlib import Path
import re

import numpy as np
import pandas as pd

DATA_FILE = Path(__file__).resolve().parent.parent / "data_real" / "vehicles.csv"
MIN_MODEL_ADS = 20

# Value attributes stated in the ad (title + description). These are the
# "trust / documentation / reconditioning" actions a seller can act on.
ATTRIBUTES = {
    "single_owner": r"\b(single|1st|first|one)\s*owner",
    "service_records": r"service\s*(record|history|book)|agent\s*maint|company\s*maint|full\s*service",
    "new_tyres": r"new\s*(tyre|tire)s?",
    "new_battery": r"new\s*batter(y|ies)",
    "accident_free": r"accident[\s-]*free|no\s*accident|non[\s-]*accident",
    "original_paint": r"original\s*(paint|body)|factory\s*paint|full\s*original",
    "needs_repair": r"need(s)?\s*(repair|work|paint|minor)|scratch|dent|body\s*work",
}

NUMERIC = ["age_years", "mileage_km", "engine_cc"]
CATEGORICAL = ["model", "fuel_type", "transmission", "condition", "body_type"]
TARGET = "price_lkr"

TARGET_MODELS = ["Axio", "Premio", "Allion", "Vitz", "Corolla", "Yaris"]


def _number(text):
    digits = re.sub(r"[^\d.]", "", str(text))
    return float(digits) if digits else np.nan


def _properties(text):
    if isinstance(text, str) and text.startswith("{"):
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return {}
    return {}


def load(path=DATA_FILE):
    raw = pd.read_csv(path, low_memory=False, on_bad_lines="skip")
    cars = raw[raw["category"] == "Cars"].copy()
    props = cars["properties"].map(_properties)
    cars = cars[props.map(lambda p: p.get("Brand")) == "Toyota"]
    props = props[cars.index]

    posted = pd.to_datetime(cars["posted_date"], errors="coerce", utc=True)
    year = props.map(lambda p: _number(p.get("Year of Manufacture")))
    df = pd.DataFrame({
        "user": cars["user"].astype(str),
        "model": props.map(lambda p: str(p.get("Model", "")).strip()),
        "trim": props.map(lambda p: p.get("Trim / Edition")),
        "year": year,
        "age_years": (posted.dt.year + (posted.dt.dayofyear - 182) / 365.25 - year).clip(lower=0),
        "mileage_km": props.map(lambda p: _number(p.get("Mileage"))),
        "engine_cc": props.map(lambda p: _number(p.get("Engine capacity"))),
        "fuel_type": props.map(lambda p: p.get("Fuel type")),
        "transmission": props.map(lambda p: p.get("Transmission")),
        "condition": props.map(lambda p: p.get("Condition")),
        "body_type": props.map(lambda p: p.get("Body type") or "Unknown"),
        "price_lkr": cars["price"].map(_number),
        "posted_date": posted,
    }, index=cars.index)

    text = (cars["title"].astype(str) + " " + cars["ad_description"].astype(str)).str.lower()
    for name, pattern in ATTRIBUTES.items():
        df[name] = text.str.contains(pattern, regex=True).astype(int)

    df = df[df["condition"].isin(["Used", "Reconditioned"])
            & df["price_lkr"].between(300_000, 100_000_000)
            & df["mileage_km"].between(0, 600_000)
            & df["age_years"].between(0, 45)
            & df["year"].notna()]
    df = df[~((df["condition"] == "Used") & (df["mileage_km"] <= 0))]
    df = df.drop_duplicates(["user", "model", "year", "mileage_km", "price_lkr"])

    counts = df["model"].value_counts()
    df["model"] = df["model"].where(df["model"].map(counts) >= MIN_MODEL_ADS, "Other")
    df["engine_cc"] = df["engine_cc"].where(df["engine_cc"].between(600, 6000))
    return df.reset_index(drop=True)
