"""Unit tests for the expert system and the full pipeline.

Run from the component folder:  python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from expert_system import run_expert_system  # noqa: E402
from fault_service import HiddenFaultService  # noqa: E402

SENSORS = dict(rpm=1800, load=45, coolant=88, engine_temp=88, voltage=14.1,
               vibration=0.08, vehicle_model="Corolla", dtc_codes=())


def sensors(**changes):
    return {**SENSORS, **changes}


def fault_names(result):
    return {f["name"] for f in result["faults"]}


def rules_fired(result):
    return [t["rule"].split()[0] for t in result["trace"]]


class DetectionRules(unittest.TestCase):

    def test_healthy_reading_fires_no_fault(self):
        self.assertEqual(fault_names(run_expert_system(sensors())), set())

    def test_critical_vibration_is_high_severity(self):
        r = run_expert_system(sensors(vibration=0.6))
        self.assertIn("Abnormal_Vibration", fault_names(r))
        self.assertIn("High", {s["level"] for s in r["severities"]})

    def test_vitz_uses_higher_vibration_threshold(self):
        self.assertIn("Abnormal_Vibration", fault_names(run_expert_system(sensors(vibration=0.46))))
        self.assertNotIn("Abnormal_Vibration",
                         fault_names(run_expert_system(sensors(vibration=0.46, vehicle_model="Vitz"))))

    def test_warm_up_blocks_idle_rules(self):
        r = run_expert_system(sensors(rpm=930, load=30, coolant=60))
        self.assertNotIn("High_Idle", fault_names(r))
        self.assertIn("D4", rules_fired(r))


class FusionAndMitigation(unittest.TestCase):

    def test_anomaly_without_rule_is_hidden_fault(self):
        r = run_expert_system(sensors(), anomaly=dict(score=3.0, threshold=0.0, flagged=True))
        self.assertEqual(fault_names(r), {"Hidden_Anomaly"})

    def test_anomaly_while_cold_is_only_a_note(self):
        r = run_expert_system(sensors(coolant=50), anomaly=dict(score=3.0, threshold=0.0, flagged=True))
        self.assertEqual(fault_names(r), set())
        self.assertIn("F4", rules_fired(r))

    def test_classifier_fault_gets_shap_targeted_action(self):
        r = run_expert_system(
            sensors(voltage=15.3),
            prediction=dict(fault="Charging_System_Warning", confidence=0.99),
            factors=[dict(model="classifier", feature="battery_voltage_v", label="Battery voltage",
                          value=15.3, impact=6.9, rank=1)],
        )
        targeted = [a for a in r["actions"] if a["kind"] == "targeted"]
        self.assertEqual(len(targeted), 1)
        self.assertEqual(targeted[0]["feature"], "voltage")
        self.assertIn("High", {s["level"] for s in r["severities"]})   # overcharging escalation

    def test_same_fault_different_cause_gives_different_action(self):
        def targeted_for(feature):
            r = run_expert_system(
                sensors(),
                prediction=dict(fault="Cooling_System_Warning", confidence=0.9),
                factors=[dict(model="classifier", feature=feature, label=feature, value=1.0, impact=1.0, rank=1)],
            )
            return [a["text"] for a in r["actions"] if a["kind"] == "targeted"]
        self.assertNotEqual(targeted_for("engine_temp_c"), targeted_for("engine_load_pct"))

    def test_hidden_anomaly_is_named_by_shap(self):
        # Vibration spread over several features still wins as a group
        factors = [
            dict(model="anomaly", feature="engine_rpm", label="Engine RPM", value=2000, impact=0.9, rank=1),
            dict(model="anomaly", feature="vibration_x", label="Vibration X", value=0.4, impact=0.6, rank=2),
            dict(model="anomaly", feature="vibration_magnitude", label="Vibration level", value=0.6, impact=0.5, rank=3),
            dict(model="anomaly", feature="coolant_temp", label="Coolant temperature", value=88, impact=-0.2, rank=4),
        ]
        r = run_expert_system(sensors(), anomaly=dict(score=3.0, threshold=0.0, flagged=True), factors=factors)
        self.assertEqual(fault_names(r), {"Hidden_Anomaly"})
        self.assertEqual([(c["fault"], c["group"]) for c in r["causes"]], [("Hidden_Anomaly", "vibration")])
        self.assertIn("X1", rules_fired(r))
        targeted = [a for a in r["actions"] if a["kind"] == "targeted"]
        self.assertEqual([a["feature"] for a in targeted], ["vibration"])

    def test_rule_faults_get_no_xai_cause(self):
        r = run_expert_system(sensors(vibration=0.6), factors=[
            dict(model="anomaly", feature="vibration_x", label="Vibration X", value=0.4, impact=1.0, rank=1)])
        self.assertEqual(r["causes"], [])

    def test_cause_that_does_not_fit_the_fault_is_low_reliability(self):
        def reliability(feature):
            r = run_expert_system(
                sensors(), prediction=dict(fault="Cooling_System_Warning", confidence=0.95),
                factors=[dict(model="classifier", feature=feature, label=feature, value=1.0, impact=1.0, rank=1)])
            return [x["level"] for x in r["reliability"]], rules_fired(r)
        levels, fired = reliability("engine_load_pct")
        self.assertEqual(levels, ["Low"])
        self.assertIn("X2", fired)
        self.assertEqual(reliability("engine_temp_c")[0], [])

    def test_every_fault_has_a_mitigation_plan(self):
        r = run_expert_system(sensors(vibration=0.5),
                              prediction=dict(fault="Cooling_System_Warning", confidence=0.9))
        for name in fault_names(r):
            self.assertTrue(any(a["fault"] == name for a in r["actions"]), name)


class Pipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.service = HiddenFaultService()

    def test_result_has_explanations_and_reasoning(self):
        r = self.service.assess(dict(engine_rpm=800, engine_load_pct=5, coolant_temp_c=82, battery_voltage_v=15.3))
        self.assertEqual(r["primary_fault"], "Charging_System_Warning")
        self.assertEqual(r["explanations"]["classifier"]["factors"][0]["feature"], "battery_voltage_v")
        self.assertGreater(r["engine"]["rules_fired"], 0)
        self.assertLess(r["latency_ms"], 2000)      # proposal target: <= 2 s

    def test_issues_report_the_likely_cause(self):
        r = self.service.assess(dict(engine_rpm=800, engine_load_pct=5, coolant_temp_c=82, battery_voltage_v=15.3))
        cause = r["issues"][0]["likely_cause"]
        self.assertEqual(cause["sensor_group"], "voltage")
        self.assertGreater(cause["share"], 0.5)

    def test_counterfactual_gives_a_repair_target(self):
        r = self.service.assess(dict(engine_rpm=800, engine_load_pct=5, coolant_temp_c=82, battery_voltage_v=15.3))
        issue = r["issues"][0]
        change = issue["counterfactual"]["changes"][0]
        self.assertEqual((change["group"], change["direction"]), ("voltage", "down"))
        self.assertTrue(14.0 <= change["to"] < 15.3)
        self.assertTrue(any(a.startswith("Repair target:") for a in issue["immediate_actions"]))
        self.assertEqual(issue["reliability"]["level"], "Normal")

    def test_missing_inputs_raise(self):
        with self.assertRaises(ValueError):
            self.service.assess({"engine_rpm": 800})


if __name__ == "__main__":
    unittest.main()
