"""Hybrid OBD-II assessment: threshold rules + anomaly detection model.

Rules catch known faults with a clear reason. The anomaly model
(trained on normal readings only) catches unusual patterns that no
rule describes, i.e. possible hidden faults.
"""

from pathlib import Path
import json
import math

import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "obd_anomaly_model.joblib"
METADATA_PATH = BASE_DIR / "models" / "obd_anomaly_metadata.json"
FUSION_CONFIG_PATH = BASE_DIR / "models" / "fusion_config.json"

# Thresholds taken from the label_reason column of
# toyota_obd_original_labeled.csv
WARM_ENGINE_TEMP_C = 80          # below this the engine is warming up
VIBRATION_WARNING_G = 0.44
VIBRATION_WARNING_G_BY_MODEL = {
    "Vitz": 0.48,                # 1KR-FE 3-cylinder runs rougher
}
VIBRATION_CRITICAL_G = 0.54
LUGGING_LOAD_PCT = 85
LUGGING_MAX_RPM = 1500
HOT_COOLANT_C = 95
HOT_MIN_LOAD_PCT = 90
IDLE_MAX_LOAD_PCT = 45
IDLE_MAX_RPM = 1000
IDLE_SPEC_MIN_RPM = 650
IDLE_SPEC_MAX_RPM_WITH_AC = 900

# Rule severity -> priority (higher wins)
RULE_PRIORITY = {"Critical": 2, "Warning": 1}


def vibration_magnitude(x, y, z):
    return math.sqrt(x ** 2 + y ** 2 + z ** 2)


def check_rules(readings, vehicle_model=None):
    """Return a list of rule findings for one reading.

    Each finding is {"fault", "severity", "reason"}.
    """
    rpm = readings["engine_rpm"]
    load = readings["engine_load"]
    coolant = readings["coolant_temp"]
    vibration = readings["vibration_magnitude"]

    findings = []

    warning_g = VIBRATION_WARNING_G_BY_MODEL.get(
        vehicle_model, VIBRATION_WARNING_G
    )
    if vibration >= VIBRATION_CRITICAL_G:
        findings.append({
            "fault": "Abnormal_Vibration",
            "severity": "Critical",
            "reason": (
                f"Vibration {vibration:.2f}g >= {VIBRATION_CRITICAL_G}g "
                "(mount/misfire)"
            ),
        })
    elif vibration >= warning_g:
        findings.append({
            "fault": "Abnormal_Vibration",
            "severity": "Warning",
            "reason": f"Vibration {vibration:.2f}g >= {warning_g}g",
        })

    if load >= LUGGING_LOAD_PCT and rpm < LUGGING_MAX_RPM:
        findings.append({
            "fault": "Engine_Lugging",
            "severity": "Warning",
            "reason": (
                f"Load {load:.0f}% >= {LUGGING_LOAD_PCT}% "
                f"below {LUGGING_MAX_RPM} rpm"
            ),
        })

    # Temperature and idle rules only apply to a warm engine
    if coolant < WARM_ENGINE_TEMP_C:
        return findings

    if coolant >= HOT_COOLANT_C and load >= HOT_MIN_LOAD_PCT:
        findings.append({
            "fault": "Running_Hot",
            "severity": "Warning",
            "reason": (
                f"Coolant {coolant:.0f}C high under {load:.0f}% load "
                "(fan/radiator check)"
            ),
        })

    is_idle = load < IDLE_MAX_LOAD_PCT and rpm < IDLE_MAX_RPM
    if is_idle and rpm < IDLE_SPEC_MIN_RPM:
        findings.append({
            "fault": "Rough_Idle",
            "severity": "Warning",
            "reason": (
                f"Warm idle {rpm:.0f} rpm below spec "
                f"{IDLE_SPEC_MIN_RPM}-800"
            ),
        })
    elif is_idle and rpm > IDLE_SPEC_MAX_RPM_WITH_AC:
        findings.append({
            "fault": "High_Idle",
            "severity": "Warning",
            "reason": (
                f"Warm idle {rpm:.0f} rpm above spec even with A/C "
                "(vacuum leak/IACV)"
            ),
        })

    return findings


class OBDAssessor:
    """Loads the anomaly model once and assesses readings."""

    def __init__(self, model_path=MODEL_PATH, metadata_path=METADATA_PATH):
        self.model = joblib.load(model_path)
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
        self.features = metadata["features"]
        self.threshold = metadata["threshold"]
        # Threshold calibrated on unseen vehicles (benchmark/tune_fusion.py), if available
        if FUSION_CONFIG_PATH.exists():
            with open(FUSION_CONFIG_PATH, encoding="utf-8") as f:
                self.threshold = json.load(f)["anomaly_threshold"]

    def anomaly_score(self, readings):
        """Higher score = more abnormal."""
        row = pd.DataFrame([readings])[self.features]
        return float(-self.model.decision_function(row)[0])

    def assess(self, readings, vehicle_model=None):
        """Combine rules and the anomaly model for one reading.

        readings needs engine_rpm, engine_load, coolant_temp and
        vibration_x/y/z. vibration_magnitude is added if missing.
        """
        readings = dict(readings)
        readings.setdefault(
            "vibration_magnitude",
            vibration_magnitude(
                readings["vibration_x"],
                readings["vibration_y"],
                readings["vibration_z"],
            ),
        )

        findings = check_rules(readings, vehicle_model)
        score = self.anomaly_score(readings)
        is_anomaly = score >= self.threshold
        warming_up = readings["coolant_temp"] < WARM_ENGINE_TEMP_C

        if findings:
            main = max(
                findings, key=lambda f: RULE_PRIORITY[f["severity"]]
            )
            fault = main["fault"]
            status = main["severity"]
            source = "Rule + AI" if is_anomaly else "Rule"
        elif is_anomaly and not warming_up:
            # No rule explains it: possible hidden fault.
            # Cold readings are rare in the training data, so a cold
            # engine alone is not reported as a hidden fault.
            fault = "Hidden_Anomaly"
            status = "Warning"
            source = "AI"
        else:
            fault = "Normal"
            status = "Normal"
            source = "Rule + AI"

        return {
            "fault": fault,
            "status": status,
            "source": source,
            "rule_findings": findings,
            "anomaly_score": score,
            "anomaly_threshold": self.threshold,
            "is_anomaly": bool(is_anomaly),
            "warming_up": warming_up,
            "readings": readings,
        }


if __name__ == "__main__":
    # Compare the rules with the labels in the dataset
    df = pd.read_csv(
        BASE_DIR / "raw_data" / "toyota_obd_original_labeled.csv"
    )

    def first_rule_fault(row):
        findings = check_rules(row, row["vehicle_model"])
        if not findings:
            return "Normal"
        return max(
            findings, key=lambda f: RULE_PRIORITY[f["severity"]]
        )["fault"]

    labels = df["fault_label"].replace("Warm_Up", "Normal")
    predicted = df.apply(first_rule_fault, axis=1)

    print("===== RULES vs DATASET LABELS =====")
    print(f"Agreement: {(predicted == labels).mean():.2%}")
    print(pd.crosstab(labels, predicted, rownames=["label"],
                      colnames=["rules"]).to_string())

    assessor = OBDAssessor()
    examples = [
        ("Corolla", {"engine_rpm": 1800, "engine_load": 45,
                     "coolant_temp": 88, "vibration_x": 0.05,
                     "vibration_y": 0.04, "vibration_z": 0.06}),
        ("Axio", {"engine_rpm": 2546, "engine_load": 80.4,
                  "coolant_temp": 86, "vibration_x": 0.35,
                  "vibration_y": 0.30, "vibration_z": 0.35}),
        ("Allion", {"engine_rpm": 930, "engine_load": 32,
                    "coolant_temp": 88, "vibration_x": 0.05,
                    "vibration_y": 0.05, "vibration_z": 0.1}),
        ("Yaris", {"engine_rpm": 3400, "engine_load": 25,
                   "coolant_temp": 84, "vibration_x": -0.3,
                   "vibration_y": 0.3, "vibration_z": -0.1}),
    ]

    print("\n===== EXAMPLE ASSESSMENTS =====")
    for model_name, readings in examples:
        result = assessor.assess(readings, model_name)
        print(
            f"{model_name}: {result['fault']} ({result['status']}, "
            f"{result['source']}) | score {result['anomaly_score']:.3f} "
            f"/ threshold {result['anomaly_threshold']:.3f}"
        )
        for finding in result["rule_findings"]:
            print("   rule:", finding["reason"])
