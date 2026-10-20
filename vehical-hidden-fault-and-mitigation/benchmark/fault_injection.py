"""Fault injection benchmark data.

Ground truth must not come from any method being evaluated. The OBD-II
labels in toyota_obd_original_labeled.csv were made with the same
thresholds the expert system uses, so testing on them would favour the
rules. Instead we take real *normal* readings and inject faults we
control, at five severity levels. The injected fault is the ground truth.

Assumption: the OBD-II log has no battery voltage, so a normal charging
voltage is sampled from the Normal rows of the battery dataset
(mean 13.99 V, sd 0.25 V). Engine temperature = coolant temperature, as
in fault_service.assess().
"""

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
OBD_FILE = BASE_DIR / "raw_data" / "toyota_obd_original_labeled.csv"
BATTERY_FILE = BASE_DIR / "cleaned_data" / "AutoSense_Toyota_Battery_Voltage_Deduplicated.csv"

FAULT_TYPES = ["Charging", "Cooling", "Vibration"]
SEVERITY_LEVELS = [1, 2, 3, 4, 5]

# Size of the injected change per severity level (index 0 = level 1)
UNDERCHARGE_DROP_V = [0.3, 0.6, 0.9, 1.3, 1.8]
OVERCHARGE_RISE_V = [0.25, 0.5, 0.75, 1.0, 1.4]
COOLANT_RISE_C = [4, 8, 12, 16, 20]
VIBRATION_SCALE = [1.3, 1.6, 1.9, 2.2, 2.6]

VOLTAGE_CLIP = (13.3, 14.6)


def load_normal_readings():
    """Real OBD-II readings labelled normal, plus a sampled normal voltage."""
    obd = pd.read_csv(OBD_FILE)
    normal = obd[obd["fault"] == 0].reset_index(drop=True)

    battery = pd.read_csv(BATTERY_FILE)
    volts = battery.loc[battery["fault_label"] == "Normal", "battery_voltage_v"]

    rng = np.random.default_rng(0)
    voltage = rng.normal(volts.mean(), volts.std(), len(normal)).clip(*VOLTAGE_CLIP)

    return pd.DataFrame({
        "vehicle_id": normal["vehicle_id"],
        "vehicle_model": normal["vehicle_model"],
        "engine_rpm": normal["engine_rpm"].astype(float),
        "engine_load_pct": normal["engine_load"].astype(float),
        "coolant_temp_c": normal["coolant_temp"].astype(float),
        "engine_temp_c": normal["coolant_temp"].astype(float),
        "battery_voltage_v": voltage.round(2),
        "vibration_x_g": normal["vibration_x"],
        "vibration_y_g": normal["vibration_y"],
        "vibration_z_g": normal["vibration_z"],
    })


def inject(row, fault, severity, rng):
    """Return a copy of one reading with a fault of the given severity."""
    row = row.copy()
    i = severity - 1
    if fault == "Charging":
        if rng.random() < 0.5:
            row["battery_voltage_v"] -= UNDERCHARGE_DROP_V[i]
        else:
            row["battery_voltage_v"] += OVERCHARGE_RISE_V[i]
    elif fault == "Cooling":
        row["coolant_temp_c"] += COOLANT_RISE_C[i]
        row["engine_temp_c"] += COOLANT_RISE_C[i]
    elif fault == "Vibration":
        for axis in ("vibration_x_g", "vibration_y_g", "vibration_z_g"):
            row[axis] *= VIBRATION_SCALE[i]
    else:
        raise ValueError(f"Unknown fault {fault}")
    return row


def build_test_set(base, rng):
    """Every base reading once clean, and once per fault type at a random severity."""
    rows = []
    for _, row in base.iterrows():
        clean = row.copy()
        clean["true_fault"], clean["severity"] = "Normal", 0
        rows.append(clean)
        for fault in FAULT_TYPES:
            severity = int(rng.choice(SEVERITY_LEVELS))
            faulty = inject(row, fault, severity, rng)
            faulty["true_fault"], faulty["severity"] = fault, severity
            rows.append(faulty)
    out = pd.DataFrame(rows).reset_index(drop=True)
    out["vibration_magnitude_g"] = np.sqrt(
        out["vibration_x_g"] ** 2 + out["vibration_y_g"] ** 2 + out["vibration_z_g"] ** 2
    )
    return out
