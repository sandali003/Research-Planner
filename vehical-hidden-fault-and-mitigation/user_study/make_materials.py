"""Builds the scenario cards for the XAI user study from the live system's output.

Each scenario is shown in one of three versions:
  A  Scanner style: stored trouble codes only (what an OBD-II code reader shows)
  B  Prediction:    fault name, confidence and severity
  C  Explainable:   B + likely cause (SHAP), repair target (counterfactual),
                    reliability check and the mitigation plan
Writes user_study/scenarios.md and user_study/scenarios.json.

Run (from the component folder):  python user_study/make_materials.py
"""

from pathlib import Path
import json
import sys

STUDY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDY_DIR.parent))

from fault_service import HiddenFaultService  # noqa: E402

# readings, the codes a scanner would show at this stage, the true problem
# (answer key for Q1) and the recommended decision (answer key for Q2, to be
# confirmed with the mechanics before the study)
SCENARIOS = [
    {
        "id": "S1", "title": "Idling at a car sale",
        "inputs": dict(engine_rpm=800, engine_load_pct=5, coolant_temp_c=82, battery_voltage_v=15.3),
        "scanner_codes": ["P0563 System Voltage High"],
        "true_problem": "Battery / charging system", "best_decision": "Negotiate and repair the named part",
    },
    {
        "id": "S2", "title": "Short test drive in town",
        "inputs": dict(engine_rpm=900, engine_load_pct=20, coolant_temp_c=88, battery_voltage_v=12.5),
        "scanner_codes": [],
        "true_problem": "Battery / charging system", "best_decision": "Negotiate and repair the named part",
    },
    {
        "id": "S3", "title": "After a 20-minute drive",
        "inputs": dict(engine_rpm=1800, engine_load_pct=45, coolant_temp_c=104, battery_voltage_v=14.0,
                       vibration_x_g=0.05, vibration_y_g=0.04, vibration_z_g=0.06),
        "scanner_codes": [],
        "true_problem": "Cooling system", "best_decision": "Get a full inspection before buying",
    },
    {
        "id": "S4", "title": "Highway speed",
        "inputs": dict(engine_rpm=3400, engine_load_pct=25, coolant_temp_c=84, battery_voltage_v=14.0,
                       vibration_x_g=-0.3, vibration_y_g=0.3, vibration_z_g=-0.1),
        "scanner_codes": [],
        "true_problem": "Engine mounts / ignition (vibration)", "best_decision": "Negotiate and repair the named part",
    },
    {
        "id": "S5", "title": "Healthy car, normal driving",
        "inputs": dict(engine_rpm=1800, engine_load_pct=45, coolant_temp_c=88, battery_voltage_v=14.1,
                       vibration_x_g=0.05, vibration_y_g=0.04, vibration_z_g=0.06),
        "scanner_codes": [],
        "true_problem": "No problem", "best_decision": "Buy",
    },
    {
        "id": "S6", "title": "Climbing a hill, heavily loaded",
        "inputs": dict(engine_rpm=2689, engine_load_pct=80, coolant_temp_c=97, battery_voltage_v=13.73,
                       vibration_x_g=0.1024, vibration_y_g=0.2383, vibration_z_g=-0.0079),
        "scanner_codes": [],
        "true_problem": "No problem (warm engine under heavy load)",
        "best_decision": "Take another reading before deciding",
    },
]

READINGS = [
    ("engine_rpm", "Engine speed", "rpm", 0), ("engine_load_pct", "Engine load", "%", 0),
    ("coolant_temp_c", "Coolant temperature", "°C", 0), ("battery_voltage_v", "Battery voltage", "V", 2),
]


def readings_table(inputs):
    lines = ["| Reading | Value |", "|---|---|"]
    for key, label, unit, dp in READINGS:
        if inputs.get(key) is not None:
            lines.append(f"| {label} | {inputs[key]:.{dp}f} {unit} |")
    if inputs.get("vibration_x_g") is not None:
        lines.append(f"| Vibration (x / y / z) | {inputs['vibration_x_g']:.2f} / {inputs['vibration_y_g']:.2f} / "
                     f"{inputs['vibration_z_g']:.2f} g |")
    return "\n".join(lines)


def version_a(s):
    codes = s["scanner_codes"]
    return "**Trouble codes:** " + (", ".join(codes) if codes else "No trouble codes stored.")


def version_b(result):
    if not result["issues"]:
        return "**Result:** No fault found."
    lines = []
    for i in result["issues"]:
        conf = f", confidence {i['confidence'] * 100:.0f}%" if i["confidence"] is not None else ""
        lines.append(f"- **{i['display_name'].split(':')[0]}**{conf}, severity {i['severity']}")
    return "**Result:** Fault detected\n\n" + "\n".join(lines)


def version_c(result):
    if not result["issues"]:
        notes = "".join(f"\n- {n}" for n in result["notes"])
        return "**Result:** No fault found." + (f"\n\nNotes:{notes}" if notes else "")
    blocks = []
    for i in result["issues"]:
        conf = f", confidence {i['confidence'] * 100:.0f}%" if i["confidence"] is not None else ""
        b = [f"**{i['display_name']}**{conf}, severity {i['severity']} (act: {i['timeframe']})"]
        if i.get("reliability") and i["reliability"]["level"] == "Low":
            b.append(f"- ⚠️ **Low reliability:** {i['reliability']['reason']}")
        if i.get("likely_cause"):
            c = i["likely_cause"]
            b.append(f"- **Likely cause (AI explanation):** {c['label']} ({c['share'] * 100:.0f}% of the result)")
        if i.get("counterfactual"):
            b.append(f"- **What needs to change:** {i['counterfactual']['text']}")
        b.append("- **What to do now:**" + "".join(f"\n  - {a}" for a in i["immediate_actions"]))
        b.append("- **To make it last:**" + "".join(f"\n  - {t}" for t in i["longevity_tips"]))
        blocks.append("\n".join(b))
    return "\n\n".join(blocks)


def main():
    service = HiddenFaultService()
    cards, out = [], []
    for s in SCENARIOS:
        result = service.assess(s["inputs"])
        cards.append({**s, "system_output": {k: result[k] for k in ("status", "primary_fault", "issues", "notes")}})
        out += [
            f"## {s['id']}: {s['title']}", "",
            readings_table(s["inputs"]), "",
            "### Version A (scanner)", "", version_a(s), "",
            "### Version B (prediction)", "", version_b(result), "",
            "### Version C (explainable system)", "", version_c(result), "",
            f"<sub>Answer key (researcher only): problem = {s['true_problem']}; "
            f"recommended decision = {s['best_decision']}</sub>", "", "---", "",
        ]

    header = [
        "# XAI user study: scenario cards", "",
        "Generated from the live hidden fault system (`python user_study/make_materials.py`). "
        "Each participant sees every scenario once, in one version; the version per scenario rotates "
        "between participants (see protocol.md). Remove the answer key lines before printing.", "", "---", "",
    ]
    (STUDY_DIR / "scenarios.md").write_text("\n".join(header + out), encoding="utf-8")
    (STUDY_DIR / "scenarios.json").write_text(json.dumps(cards, indent=2, default=float), encoding="utf-8")
    print(f"Wrote {len(SCENARIOS)} scenarios to {STUDY_DIR}")


if __name__ == "__main__":
    main()
