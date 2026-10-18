
import streamlit as st
import joblib
import pandas as pd

from mitigation_rules import get_mitigation_recommendation


# Model path
MODEL_PATH = "models/autosense_fault_model.joblib"


# Page configuration
st.set_page_config(
    page_title="AutoSense AI",
    page_icon="🚗",
    layout="wide"
)


# Load trained model
@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)


# Application heading
st.title("🚗 AutoSense AI")
st.subheader(
    "AI-Based Hidden Fault Prediction and Mitigation System"
)

st.write(
    "Enter vehicle sensor readings below to predict a possible "
    "fault and receive a recommended mitigation action."
)

st.divider()


# Load model safely
try:
    model = load_model()

except Exception as e:
    st.error(f"Could not load the trained model: {e}")
    st.stop()


# Sensor input form
st.markdown("### 🔧 Vehicle Sensor Readings")

with st.form("sensor_form"):

    col1, col2 = st.columns(2)

    with col1:
        engine_rpm = st.number_input(
            "Engine RPM",
            min_value=0,
            max_value=10000,
            value=1500,
            step=100
        )

        battery_voltage = st.number_input(
            "Battery Voltage (V)",
            min_value=0.0,
            max_value=30.0,
            value=13.8,
            step=0.1,
            format="%.1f"
        )

    with col2:
        engine_temp = st.number_input(
            "Engine Temperature (°C)",
            min_value=-50.0,
            max_value=250.0,
            value=85.0,
            step=1.0
        )

        engine_load = st.number_input(
            "Engine Load (%)",
            min_value=0.0,
            max_value=100.0,
            value=40.0,
            step=1.0
        )

    submitted = st.form_submit_button(
        "🔍 Predict Fault",
        type="primary",
        use_container_width=True
    )


# Prediction and mitigation
if submitted:

    # Prepare sensor data in the model's expected format
    input_data = pd.DataFrame([{
        "engine_rpm": engine_rpm,
        "battery_voltage_v": battery_voltage,
        "engine_temp_c": engine_temp,
        "engine_load_pct": engine_load
    }])

    try:
        prediction = model.predict(input_data)[0]

        # Prediction result
        st.divider()
        st.markdown("## 📊 Prediction Result")

        if prediction == "Normal":
            st.success(
                f"Predicted Condition: {prediction}"
            )
        else:
            st.warning(
                f"Predicted Fault: {prediction.replace('_', ' ')}"
            )

        # Display input readings
        st.markdown("### Submitted Sensor Values")

        result_col1, result_col2, result_col3, result_col4 = (
            st.columns(4)
        )

        result_col1.metric(
            "Engine RPM",
            f"{engine_rpm} RPM"
        )

        result_col2.metric(
            "Battery Voltage",
            f"{battery_voltage:.1f} V"
        )

        result_col3.metric(
            "Engine Temperature",
            f"{engine_temp:.1f} °C"
        )

        result_col4.metric(
            "Engine Load",
            f"{engine_load:.1f}%"
        )

        # Get mitigation recommendation using the actual function
        mitigation = get_mitigation_recommendation(
            prediction
        )

        # Mitigation section
        st.markdown("## 🛠️ Mitigation Recommendation")

        st.write(
            "**Severity:**",
            mitigation["severity"]
        )

        st.write(
            "**Message:**",
            mitigation["message"]
        )

        st.info(
            f"**Recommended Action:** {mitigation['action']}"
        )

        # Safety and research disclaimer
        st.warning(
            "Research prototype only. This prediction is based on "
            "the trained dataset and does not confirm a real vehicle "
            "fault or guarantee that the vehicle is fault-free. "
            "Consult a qualified technician when a fault is suspected."
        )

    except Exception as e:
        st.error(
            f"An error occurred during prediction or mitigation: {e}"
        )


# Footer
st.divider()

st.caption(
    "AutoSense AI | AI-Based Hidden Fault Prediction and "
    "Mitigation System | Research Prototype"
)
