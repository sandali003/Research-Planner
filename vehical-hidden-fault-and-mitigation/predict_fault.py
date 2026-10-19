
import joblib
import pandas as pd

from mitigation_rules import get_mitigation_recommendation

MODEL_PATH = "models/autosense_fault_model.joblib"

model = joblib.load(MODEL_PATH)

print("\n=== AutoSense AI Fault Prediction System ===")
print("Enter the vehicle sensor readings below.\n")

try:
    engine_rpm = float(input("Engine RPM: "))
    battery_voltage_v = float(input("Battery voltage (V): "))
    engine_temp_c = float(input("Engine temperature (C): "))
    engine_load_pct = float(input("Engine load (%): "))

    sensor_data = pd.DataFrame(
        [[
            engine_rpm,
            battery_voltage_v,
            engine_temp_c,
            engine_load_pct
        ]],
        columns=[
            "engine_rpm",
            "battery_voltage_v",
            "engine_temp_c",
            "engine_load_pct"
        ]
    )

    predicted_fault = model.predict(sensor_data)[0]

    probabilities = model.predict_proba(sensor_data)[0]
    confidence = float(
        probabilities[list(model.classes_).index(predicted_fault)]
    )

    recommendation = get_mitigation_recommendation(
        predicted_fault,
        confidence=confidence,
        sensor_readings=sensor_data.iloc[0].to_dict()
    )

    print("\n===== AutoSense AI Result =====")
    print("Predicted fault:", recommendation["display_name"])
    print(f"Confidence: {confidence:.0%}")
    print(
        "Severity:",
        recommendation["severity"],
        "-",
        recommendation["timeframe"]
    )
    print("Message:", recommendation["message"])

    print("\nImmediate actions:")
    for action in recommendation["immediate_actions"]:
        print("  -", action)

    print("\nLongevity tips:")
    for tip in recommendation["longevity_tips"]:
        print("  -", tip)

    for note in recommendation["notes"]:
        print("\nNote:", note)

except ValueError:
    print("Invalid input. Please enter numeric sensor values.")

except FileNotFoundError:
    print("Model file not found. Check the models folder.")
