"""Hidden fault prediction + mitigation for one window of vehicle data.

Pipeline:
  1. ML models (trained in this component)
       - XGBoost fault classifier (rpm, battery voltage, engine temp, load)
       - One-Class SVM anomaly model (rpm, load, coolant, vibration x/y/z)
  2. SHAP explains each model output (which sensors drove it)
  3. Experta expert system: detection rules, ML fusion, severity and
     mitigation rules; SHAP factors target the actions
  4. One JSON-ready result with the reasoning trace
"""

from pathlib import Path
import json
import time

import joblib
import pandas as pd

from expert_system import max_severity, run_expert_system
from explainer import AnomalyExplainer, ClassifierExplainer
from mitigation_rules import FAULT_RULES, SEVERITY_ORDER, TIMEFRAMES
from obd_assessment import OBDAssessor, vibration_magnitude

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

CLASSIFIER_PATH = MODEL_DIR / "autosense_fault_model.joblib"
CLASSIFIER_METADATA_PATH = MODEL_DIR / "model_metadata.json"
ANOMALY_METADATA_PATH = MODEL_DIR / "obd_anomaly_metadata.json"

# Inputs each model needs (keys of the request)
CLASSIFIER_INPUTS = [
    "engine_rpm", "battery_voltage_v", "engine_temp_c", "engine_load_pct",
]
OBD_INPUTS = [
    "engine_rpm", "engine_load_pct", "coolant_temp_c",
    "vibration_x_g", "vibration_y_g", "vibration_z_g",
]

# SHAP factors passed to the expert system per model
TOP_FACTORS = 3


def _has(inputs, keys):
    return all(inputs.get(k) is not None for k in keys)


def _version(path):
    return f"{path.stem}-{int(path.stat().st_mtime)}" if path.exists() else None


def _factor_facts(model, explanation):
    """Every SHAP factor (largest effect first) as expert system facts.

    All of them are needed: the root cause sums the SHAP values per sensor group.
    """
    return [
        {"model": model, "feature": f["feature"], "label": f["label"],
         "value": f["value"], "impact": f["impact"], "rank": rank}
        for rank, f in enumerate(explanation["factors"], start=1)
    ]


def _unique(items):
    return list(dict.fromkeys(items))


class HiddenFaultService:
    """Loads the models and explainers once and assesses windows of data."""

    def __init__(self):
        self.classifier = joblib.load(CLASSIFIER_PATH)
        with open(CLASSIFIER_METADATA_PATH, encoding="utf-8") as f:
            self.classifier_features = json.load(f)["features"]
        self.obd = OBDAssessor()
        self.classifier_explainer = ClassifierExplainer(self.classifier)
        self.anomaly_explainer = AnomalyExplainer(self.obd.model, self.obd.features)
        self.model_versions = {
            "fault_classifier": _version(CLASSIFIER_METADATA_PATH),
            "obd_anomaly": _version(ANOMALY_METADATA_PATH),
        }

    # -----------------------------------------------------------
    # 1 + 2. ML models and their SHAP explanations
    # -----------------------------------------------------------
    def _classify(self, inputs):
        row = pd.DataFrame([{k: inputs[k] for k in self.classifier_features}])
        prediction = str(self.classifier.predict(row)[0])
        probabilities = self.classifier.predict_proba(row)[0]
        classes = [str(c) for c in self.classifier.classes_]
        result = {
            "prediction": prediction,
            "confidence": float(probabilities[classes.index(prediction)]),
            "probabilities": {c: round(float(p), 4) for c, p in zip(classes, probabilities)},
        }
        return result, self.classifier_explainer.explain(row, prediction)

    def _anomaly(self, inputs):
        readings = {
            "engine_rpm": inputs["engine_rpm"],
            "engine_load": inputs["engine_load_pct"],
            "coolant_temp": inputs["coolant_temp_c"],
            "vibration_x": inputs["vibration_x_g"],
            "vibration_y": inputs["vibration_y_g"],
            "vibration_z": inputs["vibration_z_g"],
            "vibration_magnitude": inputs["vibration_magnitude_g"],
        }
        score = self.obd.anomaly_score(readings)
        result = {
            "score": score,
            "threshold": self.obd.threshold,
            "is_anomaly": bool(score >= self.obd.threshold),
        }
        row = pd.DataFrame([readings])[self.obd.features]
        return result, self.anomaly_explainer.explain(row)

    # -----------------------------------------------------------
    # 4. Turn the expert system's facts into issues
    # -----------------------------------------------------------
    @staticmethod
    def _issues(es, explanations):
        issues = []
        for name in _unique(f["name"] for f in es["faults"]):
            faults = [f for f in es["faults"] if f["name"] == name]
            sources = _unique(f["source"] for f in faults)
            confidences = [f["confidence"] for f in faults if f["confidence"] is not None]
            severity = max_severity(s["level"] for s in es["severities"] if s["fault"] == name)
            actions = sorted(
                (a for a in es["actions"] if a["fault"] == name),
                key=lambda a: a["priority"],
            )

            key_factors = []
            if "AI classifier" in sources and explanations.get("classifier"):
                key_factors += explanations["classifier"]["factors"][:TOP_FACTORS]
            if "AI anomaly model" in sources and explanations.get("anomaly"):
                key_factors += explanations["anomaly"]["factors"][:TOP_FACTORS]

            content = FAULT_RULES.get(name, {})
            display_name = content.get("display_name", name.replace("_", " "))
            causes = [c for c in es["causes"] if c["fault"] == name]
            likely_cause = None
            if causes:
                cause = max(causes, key=lambda c: c["share"])
                likely_cause = {"sensor_group": cause["group"], "label": cause["label"],
                                "share": cause["share"], "model": cause["model"],
                                "method": "SHAP values summed per sensor group"}
                if name == "Hidden_Anomaly":
                    display_name = f"{display_name}: likely cause {cause['label'].lower()}"

            issues.append({
                "fault": name,
                "display_name": display_name,
                "likely_cause": likely_cause,
                "sources": sources,
                "confidence": round(max(confidences), 4) if confidences else None,
                "severity": severity,
                "timeframe": TIMEFRAMES[severity],
                "message": content.get("message", ""),
                "reasons": _unique(f["reason"] for f in faults),
                "immediate_actions": _unique(a["text"] for a in actions),
                "targeted_actions": _unique(a["text"] for a in actions if a["kind"] == "targeted"),
                "longevity_tips": _unique(t["text"] for t in es["tips"] if t["fault"] == name),
                "notes": _unique(n["text"] for n in es["notes"] if n["fault"] == name),
                "key_factors": key_factors,
            })

        issues.sort(key=lambda i: SEVERITY_ORDER.index(i["severity"]), reverse=True)
        return issues

    # -----------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------
    def assess(self, inputs):
        started = time.perf_counter()
        inputs = dict(inputs)

        # The classifier was trained on engine temperature; use the
        # OBD coolant temperature when no separate engine temp is given.
        if inputs.get("engine_temp_c") is None:
            inputs["engine_temp_c"] = inputs.get("coolant_temp_c")
        if _has(inputs, ["vibration_x_g", "vibration_y_g", "vibration_z_g"]):
            inputs["vibration_magnitude_g"] = vibration_magnitude(
                inputs["vibration_x_g"], inputs["vibration_y_g"], inputs["vibration_z_g"],
            )

        run_classifier = _has(inputs, CLASSIFIER_INPUTS)
        run_anomaly = _has(inputs, OBD_INPUTS)
        if not (run_classifier or run_anomaly):
            raise ValueError(
                f"Not enough inputs. Need either {CLASSIFIER_INPUTS} or {OBD_INPUTS}."
            )

        classifier = anomaly = None
        explanations = {"classifier": None, "anomaly": None}
        factors = []

        if run_classifier:
            classifier, explanations["classifier"] = self._classify(inputs)
            if classifier["prediction"] != "Normal":
                factors += _factor_facts("classifier", explanations["classifier"])
        if run_anomaly:
            anomaly, explanations["anomaly"] = self._anomaly(inputs)
            if anomaly["is_anomaly"]:
                factors += _factor_facts("anomaly", explanations["anomaly"])

        # 3. Expert system
        es = run_expert_system(
            sensors={
                "rpm": inputs.get("engine_rpm"),
                "load": inputs.get("engine_load_pct"),
                "coolant": inputs.get("coolant_temp_c"),
                "engine_temp": inputs.get("engine_temp_c"),
                "voltage": inputs.get("battery_voltage_v"),
                "vibration": inputs.get("vibration_magnitude_g"),
                "vehicle_model": inputs.get("vehicle_model"),
                "dtc_codes": tuple(inputs.get("dtc_codes") or ()),
            },
            prediction=(
                {"fault": classifier["prediction"], "confidence": classifier["confidence"]}
                if classifier else None
            ),
            anomaly=(
                {"score": anomaly["score"], "threshold": anomaly["threshold"],
                 "flagged": anomaly["is_anomaly"]}
                if anomaly else None
            ),
            factors=factors,
        )

        issues = self._issues(es, explanations)
        notes = _unique(n["text"] for n in es["notes"] if n["fault"] is None)
        if not run_classifier:
            notes.append("Battery voltage or engine temperature missing: the fault classifier was skipped.")
        if not run_anomaly:
            notes.append("Vibration or OBD-II data missing: the rule and anomaly checks were skipped.")

        if issues:
            overall_severity = issues[0]["severity"]
            longevity_tips = _unique(t for i in issues for t in i["longevity_tips"])
        else:
            overall_severity = max_severity(
                s["level"] for s in es["severities"] if s["fault"] == "Normal"
            )
            longevity_tips = FAULT_RULES["Normal"]["longevity_tips"]

        rule_faults = {f["name"] for f in es["faults"] if f["source"] == "Rule"}
        rule_findings = [
            {
                "fault": f["name"],
                "severity": "Critical" if any(
                    s["fault"] == f["name"] and s["kind"] == "escalation" and s["level"] == "High"
                    for s in es["severities"]) else "Warning",
                "reason": f["reason"],
            }
            for f in es["faults"] if f["name"] in rule_faults and f["source"] == "Rule"
        ]

        latency_ms = (time.perf_counter() - started) * 1000

        return {
            "status": "Fault detected" if issues else "Normal",
            "primary_fault": issues[0]["fault"] if issues else "Normal",
            "overall_severity": overall_severity,
            "timeframe": TIMEFRAMES[overall_severity],
            "issues": issues,
            "longevity_tips": longevity_tips,
            "notes": notes,
            "classifier": classifier,
            "anomaly": anomaly,
            "rule_findings": rule_findings,
            "explanations": explanations,
            "reasoning": es["trace"],
            "engine": {"name": "Experta expert system", "rules_fired": len(es["trace"])},
            "models_used": [
                name for name, used in [
                    ("fault_classifier", run_classifier),
                    ("obd_rules_and_anomaly", run_anomaly),
                ] if used
            ],
            "model_versions": self.model_versions,
            "inputs": inputs,
            "latency_ms": round(latency_ms, 2),
        }


if __name__ == "__main__":
    service = HiddenFaultService()
    examples = {
        "1 healthy": dict(engine_rpm=1800, engine_load_pct=45, coolant_temp_c=88, battery_voltage_v=14.1,
                          vibration_x_g=0.05, vibration_y_g=0.04, vibration_z_g=0.06),
        "2 vibration": dict(engine_rpm=2546, engine_load_pct=80, coolant_temp_c=86, battery_voltage_v=14.0,
                            vibration_x_g=0.35, vibration_y_g=0.30, vibration_z_g=0.35, vehicle_model="Axio"),
        "3 charging": dict(engine_rpm=800, engine_load_pct=5, coolant_temp_c=82, battery_voltage_v=15.3),
        "4 high idle": dict(engine_rpm=930, engine_load_pct=32, coolant_temp_c=88, battery_voltage_v=14.0,
                            vibration_x_g=0.05, vibration_y_g=0.05, vibration_z_g=0.10),
        "5 hidden": dict(engine_rpm=3400, engine_load_pct=25, coolant_temp_c=84, battery_voltage_v=14.0,
                         vibration_x_g=-0.3, vibration_y_g=0.3, vibration_z_g=-0.1),
        "6 running hot": dict(engine_rpm=2350, engine_load_pct=95, coolant_temp_c=96, battery_voltage_v=14.0,
                              vibration_x_g=0.1, vibration_y_g=0.05, vibration_z_g=0.05),
        "7 cold engine": dict(engine_rpm=900, engine_load_pct=35, coolant_temp_c=50, battery_voltage_v=14.0,
                              vibration_x_g=0.05, vibration_y_g=0.05, vibration_z_g=0.05),
    }
    for name, inputs in examples.items():
        r = service.assess(inputs)
        print(f"\n===== {name}: {r['status']} | {r['overall_severity']} | {r['latency_ms']} ms "
              f"| rules fired {r['engine']['rules_fired']}")
        for i in r["issues"]:
            print(f"  - {i['display_name']} [{i['severity']}] {i['sources']}")
            for a in i["targeted_actions"]:
                print(f"      SHAP-targeted: {a[:70]}")
        for n in r["notes"]:
            print("  note:", n[:90])
