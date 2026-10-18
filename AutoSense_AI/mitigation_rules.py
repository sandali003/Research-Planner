
MITIGATION_RULES = {
    "Normal": {
        "severity": "No fault warning",
        "message": "No fault pattern identified by the model.",
        "action": (
            "Continue routine maintenance and monitor sensor readings. "
            "This prediction does not guarantee that the vehicle is fault-free."
        ),
    },
    "Charging_System_Warning": {
        "severity": "Warning",
        "message": "A possible charging-system issue was detected.",
        "action": (
            "Arrange an inspection of the battery, terminals, wiring, "
            "and charging system by a qualified technician."
        ),
    },
    "Cooling_System_Warning": {
        "severity": "Warning",
        "message": "A possible cooling-system issue was detected.",
        "action": (
            "If the engine is overheating, stop in a safe place and let it "
            "cool. Do not open the radiator cap while hot. Arrange an inspection."
        ),
    },
    "Engine_Abnormality_Suspected": {
        "severity": "Inspection recommended",
        "message": "The model suspects a possible engine abnormality.",
        "action": (
            "Arrange diagnostic trouble-code scanning and an inspection "
            "of relevant sensors and engine systems. Treat this as a warning, "
            "not a confirmed diagnosis."
        ),
    },
}


def get_mitigation_recommendation(predicted_fault):
    return MITIGATION_RULES.get(
        predicted_fault,
        {
            "severity": "Unknown",
            "message": "No recommendation is available for this label.",
            "action": "Request a qualified technician's assessment.",
        },
    )


if __name__ == "__main__":
    for fault in MITIGATION_RULES:
        result = get_mitigation_recommendation(fault)

        print(f"\n===== {fault} =====")
        print("Severity:", result["severity"])
        print("Message:", result["message"])
        print("Recommended action:", result["action"])
