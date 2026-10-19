
import joblib
import pandas as pd

MODEL_PATH = "models/toyota_target_score_model.joblib"

model = joblib.load(MODEL_PATH)

# Example sensor readings
sample = pd.DataFrame([{
    "Engine_Load_Percent": 50,
    "Injection_Timing": 15,
    "Fuel_Injection_Pressure": 100,
    "EGR_Rate": 10,
    "Boost_Pressure": 1.2,
    "Intake_Temperature": 35,
    "Equivalence_Ratio": 1.0,
    "Cylinder_Pressure_Peak": 80,
    "Combustion_Duration": 40,
    "Gasoline_Energy_Share": 0.8,
    "BSFC": 250,
    "NOx_Emissions": 0.5,
    "Soot_Emissions": 0.1,
    "CO_Emissions": 0.2,
    "Combustion_Stability_Index": 0.95,
    "vehicle_model": "Toyota Vitz"
}])

prediction = model.predict(sample)

print("Predicted Target Score:", round(float(prediction[0]), 4))
print("Note: This is a synthetic-data score prediction,")
print("not a confirmed engine fault diagnosis.")
