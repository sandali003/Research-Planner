"""Expert system for hidden fault detection and mitigation (Experta shell).

Knowledge base = the rules below + fault content in mitigation_rules.py.
Facts         = sensor readings, ML predictions, anomaly result and the
                SHAP factors that explain them.
Inference     = Experta forward chaining (Rete), ordered by salience:
                  100 detection   Toyota threshold rules
                   80 ML fusion   classifier faults, hidden anomalies
                   70 XAI         root cause of each AI fault (SHAP per sensor group)
                   60 severity    base severity + escalation rules
                   40 mitigation  base actions + SHAP-targeted actions
Explanation   = every fired rule is recorded in `trace` (how the plan
                was reached).
"""

from pathlib import Path
import json

from experta import AS, MATCH, NOT, TEST, Fact, KnowledgeEngine, Rule

from mitigation_rules import FAULT_RULES, LOW_CONFIDENCE_THRESHOLD, SEVERITY_ORDER
from obd_assessment import (
    HOT_COOLANT_C, HOT_MIN_LOAD_PCT, IDLE_MAX_LOAD_PCT, IDLE_MAX_RPM,
    IDLE_SPEC_MAX_RPM_WITH_AC, IDLE_SPEC_MIN_RPM, LUGGING_LOAD_PCT,
    LUGGING_MAX_RPM, VIBRATION_CRITICAL_G, VIBRATION_WARNING_G,
    VIBRATION_WARNING_G_BY_MODEL, WARM_ENGINE_TEMP_C,
)

VERY_HOT_ENGINE_C = 110
HIGH_TEMP_NOTE_C = 105
OVERCHARGE_V = 15.0
UNDERCHARGE_V = 12.4

# Classifier faults below this confidence are reported as a note, not a fault.
# Tuned on held-out vehicles by benchmark/tune_fusion.py (models/fusion_config.json).
FUSION_CONFIG_PATH = Path(__file__).resolve().parent / "models" / "fusion_config.json"
CLASSIFIER_MIN_CONFIDENCE = (
    json.loads(FUSION_CONFIG_PATH.read_text(encoding="utf-8"))["classifier_min_confidence"]
    if FUSION_CONFIG_PATH.exists() else 0.0
)

# Which model's SHAP factors explain a fault from each source
SOURCE_MODEL = {"AI classifier": "classifier", "AI anomaly model": "anomaly"}

# SHAP-targeted mitigation: what to check when a sensor is the main cause
FACTOR_ACTIONS = {
    "voltage": "Have the battery, alternator and voltage regulator tested; "
               "the voltage reading is driving this result.",
    "temperature": "Check the coolant level, radiator fan and thermostat; "
                   "the engine temperature is driving this result.",
    "load": "Avoid heavy loads and hard acceleration until it is checked; "
            "the engine load is driving this result.",
    "rpm": "Have the idle speed, throttle body and ignition checked; "
           "the engine speed is driving this result.",
    "vibration": "Have the engine mounts, spark plugs and ignition coils "
                 "checked; engine vibration is driving this result.",
}
FEATURE_GROUP = {
    "battery_voltage_v": "voltage",
    "engine_temp_c": "temperature",
    "coolant_temp": "temperature",
    "engine_load_pct": "load",
    "engine_load": "load",
    "engine_rpm": "rpm",
    "vibration_x": "vibration",
    "vibration_y": "vibration",
    "vibration_z": "vibration",
    "vibration_magnitude": "vibration",
}
GROUP_LABELS = {
    "voltage": "Battery voltage",
    "temperature": "Engine temperature",
    "load": "Engine load",
    "rpm": "Engine speed (RPM)",
    "vibration": "Engine vibration",
}


def root_causes(factors):
    """XAI root cause per model: SHAP values summed per sensor group, largest positive group.

    Same method as benchmark/run_xai_eval.py, where it named the injected
    sensor in 91-98% of anomaly-model detections.
    """
    sums = {}
    for f in factors:
        group = FEATURE_GROUP.get(f["feature"])
        if group:
            model_sums = sums.setdefault(f["model"], {})
            model_sums[group] = model_sums.get(group, 0.0) + f["impact"]
    causes = []
    for model, groups in sums.items():
        positive = {g: s for g, s in groups.items() if s > 0}
        if positive:
            group = max(positive, key=positive.get)
            causes.append({"model": model, "group": group, "label": GROUP_LABELS[group],
                           "share": round(positive[group] / sum(positive.values()), 3)})
    return causes


# ----- Fact types -----------------------------------------------------
class Sensors(Fact):
    """rpm, load, coolant, engine_temp, voltage, vibration, vehicle_model, dtc_codes"""


class Prediction(Fact):
    """fault, confidence (XGBoost classifier)"""


class Anomaly(Fact):
    """score, threshold, flagged (One-Class SVM)"""


class Factor(Fact):
    """model, feature, label, value, impact, rank (SHAP)"""


class RootCause(Fact):
    """model, group, label, share (sensor group that SHAP says drives the model output)"""


class Cause(Fact):
    """fault, model, group, label, share (likely cause reported with a fault)"""


class WarmingUp(Fact):
    pass


class Fault(Fact):
    """name, source, confidence, reason"""


class Severity(Fact):
    """fault, level, kind, reason"""


class Action(Fact):
    """fault, text, priority, kind, feature"""


class Tip(Fact):
    """fault, text"""


class Note(Fact):
    """fault (or None), text"""


def _num(*values):
    return all(v is not None for v in values)


def _vibration_warning(model):
    return VIBRATION_WARNING_G_BY_MODEL.get(model, VIBRATION_WARNING_G)


class VehicleFaultExpert(KnowledgeEngine):

    def __init__(self):
        super().__init__()
        self.trace = []

    def _log(self, rule, because):
        self.trace.append({"rule": rule, "because": because})

    # ==================================================================
    # 1. Detection rules (salience 100)
    # ==================================================================
    @Rule(Sensors(vibration=MATCH.vib),
          TEST(lambda vib: _num(vib) and vib >= VIBRATION_CRITICAL_G),
          salience=100)
    def vibration_critical(self, vib):
        reason = f"Vibration {vib:.2f}g >= {VIBRATION_CRITICAL_G}g (mount/misfire)"
        self.declare(Fault(name="Abnormal_Vibration", source="Rule", confidence=None, reason=reason))
        self.declare(Severity(fault="Abnormal_Vibration", level="High", kind="escalation", reason=reason))
        self._log("D1 Critical vibration", reason)

    @Rule(Sensors(vibration=MATCH.vib, vehicle_model=MATCH.model),
          TEST(lambda vib, model: _num(vib) and _vibration_warning(model) <= vib < VIBRATION_CRITICAL_G),
          salience=100)
    def vibration_warning(self, vib, model):
        reason = f"Vibration {vib:.2f}g >= {_vibration_warning(model)}g"
        self.declare(Fault(name="Abnormal_Vibration", source="Rule", confidence=None, reason=reason))
        self._log("D2 Abnormal vibration", reason)

    @Rule(Sensors(rpm=MATCH.rpm, load=MATCH.load),
          TEST(lambda rpm, load: _num(rpm, load) and load >= LUGGING_LOAD_PCT and rpm < LUGGING_MAX_RPM),
          salience=100)
    def lugging(self, rpm, load):
        reason = f"Load {load:.0f}% >= {LUGGING_LOAD_PCT}% below {LUGGING_MAX_RPM} rpm"
        self.declare(Fault(name="Engine_Lugging", source="Rule", confidence=None, reason=reason))
        self._log("D3 Engine lugging", reason)

    @Rule(Sensors(coolant=MATCH.coolant),
          TEST(lambda coolant: _num(coolant) and coolant < WARM_ENGINE_TEMP_C),
          salience=100)
    def warming_up(self, coolant):
        self.declare(WarmingUp())
        self.declare(Note(fault=None, text=(
            "Engine is still warming up, so idle and temperature rules were "
            "not applied. Check again once it is warm.")))
        self._log("D4 Warm-up", f"Coolant {coolant:.0f}C < {WARM_ENGINE_TEMP_C}C")

    @Rule(Sensors(coolant=MATCH.coolant, load=MATCH.load), NOT(WarmingUp()),
          TEST(lambda coolant, load: _num(coolant, load) and coolant >= HOT_COOLANT_C and load >= HOT_MIN_LOAD_PCT),
          salience=100)
    def running_hot(self, coolant, load):
        reason = f"Coolant {coolant:.0f}C high under {load:.0f}% load (fan/radiator check)"
        self.declare(Fault(name="Running_Hot", source="Rule", confidence=None, reason=reason))
        self._log("D5 Running hot", reason)

    @Rule(Sensors(rpm=MATCH.rpm, load=MATCH.load), NOT(WarmingUp()),
          TEST(lambda rpm, load: _num(rpm, load) and load < IDLE_MAX_LOAD_PCT and rpm < IDLE_SPEC_MIN_RPM),
          salience=100)
    def rough_idle(self, rpm, load):
        reason = f"Warm idle {rpm:.0f} rpm below spec {IDLE_SPEC_MIN_RPM}-800"
        self.declare(Fault(name="Rough_Idle", source="Rule", confidence=None, reason=reason))
        self._log("D6 Rough idle", reason)

    @Rule(Sensors(rpm=MATCH.rpm, load=MATCH.load), NOT(WarmingUp()),
          TEST(lambda rpm, load: _num(rpm, load) and load < IDLE_MAX_LOAD_PCT
               and IDLE_SPEC_MAX_RPM_WITH_AC < rpm < IDLE_MAX_RPM),
          salience=100)
    def high_idle(self, rpm, load):
        reason = f"Warm idle {rpm:.0f} rpm above spec even with A/C (vacuum leak/IACV)"
        self.declare(Fault(name="High_Idle", source="Rule", confidence=None, reason=reason))
        self._log("D7 High idle", reason)

    # ==================================================================
    # 2. ML fusion rules (salience 80)
    # ==================================================================
    # Salience 85 so classifier faults exist before the anomaly rules check NOT(Fault())
    @Rule(Prediction(fault=MATCH.fault, confidence=MATCH.conf),
          TEST(lambda fault, conf: fault != "Normal" and conf >= CLASSIFIER_MIN_CONFIDENCE),
          salience=85)
    def classifier_fault(self, fault, conf):
        reason = f"XGBoost classifier predicted {fault.replace('_', ' ')} ({conf:.0%} confidence)"
        self.declare(Fault(name=fault, source="AI classifier", confidence=conf, reason=reason))
        self._log("F1 Classifier fault", reason)

    @Rule(Prediction(fault=MATCH.fault, confidence=MATCH.conf),
          TEST(lambda fault, conf: fault != "Normal" and conf < CLASSIFIER_MIN_CONFIDENCE),
          salience=85)
    def classifier_unconfirmed(self, fault, conf):
        name = fault.replace("_", " ")
        self.declare(Note(fault=None, text=(
            f"Possible {name}, but the model is not confident enough ({conf:.0%}) to report it. "
            "Check again with a longer reading or a manual inspection.")))
        self._log("F1b Classifier below confidence gate",
                  f"{name} at {conf:.0%} < {CLASSIFIER_MIN_CONFIDENCE:.0%}")

    @Rule(Anomaly(flagged=True, score=MATCH.score, threshold=MATCH.thr),
          NOT(Fault()), NOT(WarmingUp()),
          salience=80)
    def hidden_anomaly(self, score, thr):
        reason = f"Anomaly score {score:.2f} above threshold {thr:.2f}; no rule or classifier explains it"
        self.declare(Fault(name="Hidden_Anomaly", source="AI anomaly model", confidence=None, reason=reason))
        self._log("F2 Hidden fault", reason)

    @Rule(Anomaly(flagged=True, score=MATCH.score), Fault(name=MATCH.name, source=MATCH.src),
          TEST(lambda src: src in ("Rule", "AI classifier")),
          salience=80)
    def anomaly_confirms_fault(self, score, name, src):
        reason = f"Anomaly model also flagged this reading (score {score:.2f})"
        self.declare(Fault(name=name, source="AI anomaly model", confidence=None, reason=reason))
        self._log("F3 AI confirms fault", f"{name} ({src}): {reason}")

    @Rule(Anomaly(flagged=True), WarmingUp(), NOT(Fault(source="Rule")),
          salience=80)
    def cold_anomaly(self):
        self.declare(Note(fault=None, text=(
            "The AI score is high mainly because the engine is cold. "
            "Check again once it is warm.")))
        self._log("F4 Cold engine anomaly", "Anomaly flagged while warming up; not reported as a fault")

    # ==================================================================
    # 2b. XAI root cause (salience 70): name the sensor behind an AI fault.
    #     For Hidden_Anomaly this turns "unusual pattern" into a named cause.
    # ==================================================================
    @Rule(Fault(name=MATCH.name, source=MATCH.source),
          RootCause(model=MATCH.model, group=MATCH.group, label=MATCH.label, share=MATCH.share),
          TEST(lambda source, model: SOURCE_MODEL.get(source) == model),
          NOT(Cause(fault=MATCH.name)),
          salience=70)
    def xai_root_cause(self, name, model, group, label, share):
        self.declare(Cause(fault=name, model=model, group=group, label=label, share=share))
        self._log("X1 XAI root cause",
                  f"{name}: SHAP ({model}) attributes {share:.0%} of the result to {label.lower()}")

    # ==================================================================
    # 3. Severity rules (salience 60)
    # ==================================================================
    @Rule(Fault(name=MATCH.name), NOT(Severity(fault=MATCH.name, kind="base")),
          salience=60)
    def base_severity(self, name):
        level = FAULT_RULES.get(name, {}).get("severity", "Medium")
        self.declare(Severity(fault=name, level=level, kind="base", reason="Knowledge base default"))
        self._log("S1 Base severity", f"{name} -> {level}")

    @Rule(Fault(name="Cooling_System_Warning"), Sensors(engine_temp=MATCH.temp),
          TEST(lambda temp: _num(temp) and temp >= VERY_HOT_ENGINE_C),
          salience=60)
    def very_hot_engine(self, temp):
        self.declare(Severity(fault="Cooling_System_Warning", level="High", kind="escalation",
                              reason=f"Engine {temp:.0f}C >= {VERY_HOT_ENGINE_C}C"))
        self.declare(Action(fault="Cooling_System_Warning", priority=0, kind="escalation", feature=None,
                            text="Engine temperature is very high. Stop driving now and do not "
                                 "restart until the engine has cooled."))
        self._log("S2 Very hot engine", f"Engine temp {temp:.0f}C >= {VERY_HOT_ENGINE_C}C -> High")

    @Rule(Fault(name="Charging_System_Warning"), Sensors(voltage=MATCH.v),
          TEST(lambda v: _num(v) and v > OVERCHARGE_V),
          salience=60)
    def overcharging(self, v):
        self.declare(Severity(fault="Charging_System_Warning", level="High", kind="escalation",
                              reason=f"Voltage {v:.1f} V > {OVERCHARGE_V} V"))
        self.declare(Action(fault="Charging_System_Warning", priority=0, kind="escalation", feature=None,
                            text="Voltage is too high (possible overcharging). This can damage the battery "
                                 "and electronics; get the charging system checked as soon as possible."))
        self._log("S3 Overcharging", f"Voltage {v:.1f} V > {OVERCHARGE_V} V -> High")

    @Rule(Fault(name="Charging_System_Warning"), Sensors(voltage=MATCH.v),
          TEST(lambda v: _num(v) and v < UNDERCHARGE_V),
          salience=60)
    def undercharging(self, v):
        self.declare(Action(fault="Charging_System_Warning", priority=0, kind="escalation", feature=None,
                            text="Voltage is low while the engine is running. The battery may not be "
                                 "charging; the car may fail to start next time."))
        self._log("S4 Undercharging", f"Voltage {v:.1f} V < {UNDERCHARGE_V} V")

    @Rule(Fault(name=MATCH.name, source="AI classifier", confidence=MATCH.conf),
          TEST(lambda conf: _num(conf) and conf < LOW_CONFIDENCE_THRESHOLD),
          salience=60)
    def low_confidence(self, name, conf):
        self.declare(Note(fault=name, text=(
            f"The model is not very confident ({conf:.0%}). Treat this result with "
            "caution and confirm it with a manual inspection.")))
        self._log("S5 Low confidence", f"{name}: {conf:.0%} < {LOW_CONFIDENCE_THRESHOLD:.0%}")

    @Rule(Prediction(fault="Normal", confidence=MATCH.conf), NOT(Fault()),
          TEST(lambda conf: _num(conf) and conf < LOW_CONFIDENCE_THRESHOLD),
          salience=50)
    def uncertain_normal(self, conf):
        self.declare(Note(fault=None, text=(
            f"The model is not very confident ({conf:.0%}) that the vehicle is normal. "
            "Confirm it with a manual inspection.")))
        self._log("S5b Uncertain normal", f"Normal at {conf:.0%} < {LOW_CONFIDENCE_THRESHOLD:.0%}")

    @Rule(Fault(name="Engine_Abnormality_Suspected"), Sensors(rpm=MATCH.rpm),
          TEST(lambda rpm: _num(rpm) and rpm < 600),
          salience=60)
    def low_rpm_note(self, rpm):
        self.declare(Note(fault="Engine_Abnormality_Suspected", text=(
            "Engine speed is lower than a normal idle, which can point to rough "
            "running or misfiring.")))
        self._log("S6 Low engine speed", f"RPM {rpm:.0f} < 600")

    @Rule(NOT(Fault()), Sensors(engine_temp=MATCH.temp),
          TEST(lambda temp: _num(temp) and temp >= HIGH_TEMP_NOTE_C),
          salience=50)
    def normal_but_hot(self, temp):
        self.declare(Severity(fault="Normal", level="Low", kind="escalation", reason=f"Engine {temp:.0f}C"))
        self.declare(Note(fault=None, text=(
            "Engine temperature is on the high side. Keep an eye on the temperature gauge.")))
        self._log("S7 Warm engine watch", f"No fault, but engine temp {temp:.0f}C >= {HIGH_TEMP_NOTE_C}C")

    @Rule(NOT(Fault()), Sensors(voltage=MATCH.v),
          TEST(lambda v: _num(v) and (v < UNDERCHARGE_V or v > OVERCHARGE_V)),
          salience=50)
    def normal_but_voltage(self, v):
        self.declare(Severity(fault="Normal", level="Low", kind="escalation", reason=f"Voltage {v:.1f} V"))
        self.declare(Note(fault=None, text=(
            "Battery voltage is outside the usual range. Consider a battery test.")))
        self._log("S8 Voltage watch", f"No fault, but voltage {v:.1f} V outside {UNDERCHARGE_V}-{OVERCHARGE_V} V")

    # ==================================================================
    # 4. Mitigation rules (salience 40)
    # ==================================================================
    @Rule(Fault(name=MATCH.name), NOT(Action(fault=MATCH.name, kind="base")),
          salience=40)
    def base_plan(self, name):
        rule = FAULT_RULES.get(name, {})
        for text in rule.get("immediate_actions", []):
            self.declare(Action(fault=name, text=text, priority=2, kind="base", feature=None))
        for text in rule.get("longevity_tips", []):
            self.declare(Tip(fault=name, text=text))
        self._log("M1 Mitigation plan", f"{name}: knowledge base actions and longevity tips")

    @Rule(Cause(fault=MATCH.name, group=MATCH.group, label=MATCH.label, share=MATCH.share),
          NOT(Action(fault=MATCH.name, kind="targeted")),
          salience=40)
    def shap_targeted_action(self, name, group, label, share):
        self.declare(Action(fault=name, text=FACTOR_ACTIONS[group], priority=1, kind="targeted", feature=group))
        self._log("M2 SHAP-targeted action",
                  f"{name}: main cause by SHAP is {label} ({share:.0%} of the explanation) -> {group} check")

    @Rule(Sensors(dtc_codes=MATCH.codes), TEST(lambda codes: bool(codes)),
          salience=40)
    def stored_dtcs(self, codes):
        self.declare(Note(fault=None, text="Stored trouble codes reported by the vehicle: " + ", ".join(codes)))
        self._log("M3 Stored trouble codes", ", ".join(codes))


def run_expert_system(sensors, prediction=None, anomaly=None, factors=()):
    """Assert the facts, run inference, and return the derived facts + trace."""
    engine = VehicleFaultExpert()
    engine.reset()
    engine.declare(Sensors(**sensors))
    if prediction:
        engine.declare(Prediction(**prediction))
    if anomaly:
        engine.declare(Anomaly(**anomaly))
    for factor in factors:
        engine.declare(Factor(**factor))
    for cause in root_causes(factors):
        engine.declare(RootCause(**cause))
    engine.run()

    facts = list(engine.facts.values())
    of_type = lambda cls: [f for f in facts if isinstance(f, cls)]  # noqa: E731
    return {
        "faults": of_type(Fault),
        "severities": of_type(Severity),
        "actions": of_type(Action),
        "tips": of_type(Tip),
        "notes": of_type(Note),
        "causes": of_type(Cause),
        "trace": engine.trace,
    }


def max_severity(levels):
    return max(levels, key=SEVERITY_ORDER.index, default="None")
