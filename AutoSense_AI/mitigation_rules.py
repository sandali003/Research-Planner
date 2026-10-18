
"""Rule-based Mitigation & Longevity Engine.

Takes the model's predicted fault (plus confidence and sensor readings)
and returns a severity level, an immediate action plan and long-term
longevity guidelines in plain, non-technical language.
"""

SEVERITY_ORDER = ["None", "Low", "Medium", "High"]

TIMEFRAMES = {
    "High": "Immediately (within 1-2 days)",
    "Medium": "Soon (within 3-7 days)",
    "Low": "Plan soon (within 1-2 weeks)",
    "None": "Routine maintenance",
}

# Below this confidence the result is shown with a caution note.
LOW_CONFIDENCE_THRESHOLD = 0.60

FAULT_RULES = {
    "Normal": {
        "display_name": "No Fault Detected",
        "severity": "None",
        "message": "No fault pattern was identified in these readings.",
        "immediate_actions": [
            "No immediate action is needed.",
        ],
        "longevity_tips": [
            "Follow the service schedule in the owner's manual.",
            "Check engine oil and coolant levels once a month.",
            "Run another inspection after long trips or if anything "
            "feels different.",
        ],
    },
    "Charging_System_Warning": {
        "display_name": "Charging System Warning",
        "severity": "Medium",
        "message": (
            "The battery voltage suggests the battery may not be "
            "charging properly."
        ),
        "immediate_actions": [
            "Have the battery and alternator (charging unit) tested "
            "at a garage.",
            "Check that the battery terminals are tight and free "
            "of white or green corrosion.",
            "Avoid using many electrical items (A/C, lights, audio) "
            "at the same time until it is checked.",
        ],
        "longevity_tips": [
            "Clean the battery terminals every few months.",
            "Avoid many very short trips; they do not give the "
            "battery time to recharge.",
            "Replace the battery every 3-4 years or when a test "
            "shows it is weak.",
            "Have the alternator belt checked at every service.",
        ],
    },
    "Cooling_System_Warning": {
        "display_name": "Cooling System Warning",
        "severity": "High",
        "message": (
            "The engine temperature is higher than normal. "
            "Overheating can seriously damage the engine."
        ),
        "immediate_actions": [
            "If the temperature gauge is high, stop in a safe place "
            "and switch off the engine.",
            "Do not open the radiator cap while the engine is hot.",
            "When the engine is cool, check the coolant level and "
            "look for leaks under the car.",
            "Have the radiator, thermostat, cooling fan and water "
            "pump inspected before long drives.",
        ],
        "longevity_tips": [
            "Use the coolant type recommended for your vehicle, "
            "not plain water.",
            "Replace the coolant at the interval in the owner's "
            "manual (usually every 2-3 years).",
            "Keep the radiator front clean from dust and leaves.",
            "Watch the temperature gauge in heavy traffic and on "
            "hills.",
        ],
    },
    "Engine_Abnormality_Suspected": {
        "display_name": "Engine Abnormality Suspected",
        "severity": "Medium",
        "message": (
            "The engine readings do not match a normal pattern. "
            "This is a warning, not a confirmed diagnosis."
        ),
        "immediate_actions": [
            "Have the engine scanned for fault codes at a garage.",
            "Have the spark plugs, ignition coils and fuel injectors "
            "checked.",
            "Avoid hard acceleration and heavy loads until it is "
            "checked.",
        ],
        "longevity_tips": [
            "Use good-quality fuel from reliable stations.",
            "Replace spark plugs and the air filter on schedule.",
            "Let the engine idle smoothly for a short time after a "
            "cold start before driving hard.",
            "Do not ignore shaking, rough idling or loss of power; "
            "check them early.",
        ],
    },
    # ----- OBD-II faults (rules + anomaly model) -----
    "Abnormal_Vibration": {
        "display_name": "Abnormal Engine Vibration",
        "severity": "Medium",
        "message": (
            "The engine is vibrating more than normal. This often "
            "points to worn engine mounts or a misfire."
        ),
        "immediate_actions": [
            "Have the engine mounts checked for cracks or worn rubber.",
            "Have the engine scanned for misfire fault codes.",
            "Have the spark plugs and ignition coils inspected.",
        ],
        "longevity_tips": [
            "Replace worn engine mounts early; they protect other "
            "parts from vibration damage.",
            "Replace spark plugs on schedule.",
            "Avoid harsh gear changes and sudden acceleration.",
        ],
    },
    "Engine_Lugging": {
        "display_name": "Engine Lugging",
        "severity": "Low",
        "message": (
            "The engine is under very high load at low speed. "
            "This strains the engine and transmission."
        ),
        "immediate_actions": [
            "Change to a lower gear (or let the automatic gearbox "
            "shift down) when climbing hills or carrying heavy loads.",
            "Avoid pressing the accelerator fully at low speed.",
        ],
        "longevity_tips": [
            "Keep the engine in its comfortable speed range under load.",
            "Do not overload the vehicle.",
            "Have the transmission fluid checked at every service.",
        ],
    },
    "Running_Hot": {
        "display_name": "Engine Running Hot Under Load",
        "severity": "Medium",
        "message": (
            "Coolant temperature is high while the engine is working "
            "hard. The cooling system may not be keeping up."
        ),
        "immediate_actions": [
            "Reduce load and watch the temperature gauge.",
            "Check that the radiator cooling fan switches on.",
            "When the engine is cool, check the coolant level and "
            "look for leaks.",
        ],
        "longevity_tips": [
            "Keep the radiator front clean from dust and leaves.",
            "Replace the coolant at the interval in the owner's manual.",
            "Have the thermostat and water pump checked at service.",
        ],
    },
    "High_Idle": {
        "display_name": "High Idle Speed",
        "severity": "Low",
        "message": (
            "The warm engine is idling faster than the Toyota "
            "specification, even allowing for the A/C."
        ),
        "immediate_actions": [
            "Have the intake checked for vacuum leaks.",
            "Have the throttle body / idle air control valve (IACV) "
            "cleaned and checked.",
        ],
        "longevity_tips": [
            "Clean the throttle body at regular services.",
            "Replace the air filter on schedule.",
        ],
    },
    "Rough_Idle": {
        "display_name": "Low / Rough Idle",
        "severity": "Low",
        "message": (
            "The warm engine is idling slower than the Toyota "
            "specification (650-800 rpm)."
        ),
        "immediate_actions": [
            "Have the spark plugs, ignition coils and injectors checked.",
            "Have the throttle body cleaned.",
        ],
        "longevity_tips": [
            "Use good-quality fuel from reliable stations.",
            "Replace spark plugs and the air filter on schedule.",
        ],
    },
    "Hidden_Anomaly": {
        "display_name": "Unusual Pattern Detected (Possible Hidden Fault)",
        "severity": "Low",
        "message": (
            "No known fault rule was triggered, but the AI model found "
            "that this combination of readings is unusual compared "
            "with healthy Toyota engines."
        ),
        "immediate_actions": [
            "Take another reading to see if the pattern repeats.",
            "If it repeats, have the vehicle scanned at a garage.",
        ],
        "longevity_tips": [
            "Run regular checks so changes are spotted early.",
            "Follow the service schedule in the owner's manual.",
        ],
    },
}

UNKNOWN_FAULT = {
    "display_name": "Unknown Result",
    "severity": "Medium",
    "message": "No recommendation is available for this result.",
    "immediate_actions": [
        "Ask a qualified technician to inspect the vehicle.",
    ],
    "longevity_tips": [],
}


def _raise_severity(current, new):
    """Severity can only be increased by sensor rules, never lowered."""
    if SEVERITY_ORDER.index(new) > SEVERITY_ORDER.index(current):
        return new
    return current


def _apply_sensor_rules(fault, readings, severity, actions, notes):
    """Adjust the plan using the actual sensor values."""
    voltage = readings.get("battery_voltage_v")
    temp = readings.get("engine_temp_c")
    rpm = readings.get("engine_rpm")

    if fault == "Cooling_System_Warning" and temp is not None:
        if temp >= 110:
            severity = _raise_severity(severity, "High")
            actions.insert(
                0,
                "Engine temperature is very high. Stop driving now "
                "and do not restart until the engine has cooled.",
            )

    if fault == "Charging_System_Warning" and voltage is not None:
        if voltage > 15.0:
            severity = _raise_severity(severity, "High")
            actions.insert(
                0,
                "Voltage is too high (possible overcharging). This "
                "can damage the battery and electronics; get the "
                "charging system checked as soon as possible.",
            )
        elif voltage < 12.4:
            actions.insert(
                0,
                "Voltage is low while the engine is running. The "
                "battery may not be charging; the car may fail to "
                "start next time.",
            )

    if fault == "Engine_Abnormality_Suspected" and rpm is not None:
        if rpm < 600:
            notes.append(
                "Engine speed is lower than a normal idle, which can "
                "point to rough running or misfiring."
            )

    vibration = readings.get("vibration_magnitude")
    if fault == "Abnormal_Vibration" and vibration is not None:
        if vibration >= 0.54:
            severity = _raise_severity(severity, "High")
            actions.insert(
                0,
                "Vibration is very high. Avoid long or fast drives "
                "until the engine mounts and ignition are checked.",
            )

    # Readings that look risky even if the model says "Normal"
    if fault == "Normal":
        if temp is not None and temp >= 105:
            severity = _raise_severity(severity, "Low")
            notes.append(
                "Engine temperature is on the high side. Keep an eye "
                "on the temperature gauge."
            )
        if voltage is not None and (voltage < 12.4 or voltage > 15.0):
            severity = _raise_severity(severity, "Low")
            notes.append(
                "Battery voltage is outside the usual range. Consider "
                "a battery test."
            )

    return severity


def get_mitigation_recommendation(
    predicted_fault,
    confidence=None,
    sensor_readings=None,
):
    """Build a JSON-ready mitigation plan for one prediction."""
    rule = FAULT_RULES.get(predicted_fault, UNKNOWN_FAULT)

    severity = rule["severity"]
    immediate_actions = list(rule["immediate_actions"])
    longevity_tips = list(rule["longevity_tips"])
    notes = []

    if sensor_readings:
        severity = _apply_sensor_rules(
            predicted_fault,
            sensor_readings,
            severity,
            immediate_actions,
            notes,
        )

    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        notes.append(
            f"The model is not very confident ({confidence:.0%}). "
            "Treat this result with caution and confirm it with a "
            "manual inspection."
        )

    return {
        "fault": predicted_fault,
        "display_name": rule["display_name"],
        "confidence": (
            round(float(confidence), 4) if confidence is not None else None
        ),
        "severity": severity,
        "timeframe": TIMEFRAMES[severity],
        "message": rule["message"],
        "immediate_actions": immediate_actions,
        "longevity_tips": longevity_tips,
        "notes": notes,
    }


if __name__ == "__main__":
    examples = [
        ("Normal", 0.97, {"engine_temp_c": 88, "battery_voltage_v": 14.0}),
        ("Charging_System_Warning", 0.95, {"battery_voltage_v": 15.3}),
        ("Cooling_System_Warning", 0.91, {"engine_temp_c": 112}),
        ("Engine_Abnormality_Suspected", 0.48, {"engine_rpm": 560}),
    ]

    for fault, confidence, readings in examples:
        result = get_mitigation_recommendation(fault, confidence, readings)

        print(f"\n===== {result['display_name']} =====")
        print("Confidence:", f"{result['confidence']:.0%}")
        print("Severity:", result["severity"], "-", result["timeframe"])
        print("Message:", result["message"])
        print("Immediate actions:")
        for action in result["immediate_actions"]:
            print("  -", action)
        print("Longevity tips:")
        for tip in result["longevity_tips"]:
            print("  -", tip)
        for note in result["notes"]:
            print("Note:", note)
