
import streamlit as st
import joblib
import pandas as pd

from mitigation_rules import get_mitigation_recommendation
from obd_assessment import OBDAssessor, vibration_magnitude


# Model path
MODEL_PATH = "models/autosense_fault_model.joblib"

VEHICLE_MODELS = ["Allion", "Axio", "Corolla", "Premio", "Vitz", "Yaris"]

SEVERITY_ICONS = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟡",
    "None": "🟢",
}


# Page configuration
st.set_page_config(
    page_title="AutoSense AI",
    page_icon="🚗",
    layout="wide"
)


# Load trained models
@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)


@st.cache_resource
def load_obd_assessor():
    return OBDAssessor()


def show_mitigation(mitigation):
    """Mitigation plan section, shared by both checks."""
    st.markdown("## 🛠️ Mitigation & Longevity Plan")

    sev_col1, sev_col2 = st.columns(2)

    sev_col1.metric(
        "Severity",
        f"{SEVERITY_ICONS[mitigation['severity']]} "
        f"{mitigation['severity']}"
    )

    sev_col2.metric(
        "Act",
        mitigation["timeframe"]
    )

    st.write(mitigation["message"])

    for note in mitigation["notes"]:
        st.caption(f"⚠️ {note}")

    plan_col1, plan_col2 = st.columns(2)

    with plan_col1:
        st.markdown("### Immediate Actions")
        for action in mitigation["immediate_actions"]:
            st.markdown(f"- {action}")

    with plan_col2:
        st.markdown("### Longevity Tips")
        for tip in mitigation["longevity_tips"]:
            st.markdown(f"- {tip}")

    # Safety and research disclaimer
    st.warning(
        "Research prototype only. This prediction is based on "
        "the trained dataset and does not confirm a real vehicle "
        "fault or guarantee that the vehicle is fault-free. "
        "Consult a qualified technician when a fault is suspected."
    )


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

battery_tab, obd_tab = st.tabs([
    "🔋 Battery & Engine Check",
    "📳 OBD-II Vibration Check",
])


# ===============================================================
# Tab 1: Battery & engine fault classifier
# ===============================================================
with battery_tab:

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

            # Probability of the predicted class
            probabilities = model.predict_proba(input_data)[0]
            class_index = list(model.classes_).index(prediction)
            confidence = float(probabilities[class_index])

            mitigation = get_mitigation_recommendation(
                prediction,
                confidence=confidence,
                sensor_readings=input_data.iloc[0].to_dict()
            )

            # Prediction result
            st.divider()
            st.markdown("## 📊 Prediction Result")

            result_text = (
                f"{mitigation['display_name']} "
                f"(confidence {confidence:.0%})"
            )

            if prediction == "Normal":
                st.success(result_text)
            else:
                st.warning(result_text)

            st.progress(confidence, text="Model confidence")

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

            show_mitigation(mitigation)

        except Exception as e:
            st.error(
                f"An error occurred during prediction or mitigation: {e}"
            )


# ===============================================================
# Tab 2: OBD-II hybrid check (rules + anomaly model)
# ===============================================================
with obd_tab:

    try:
        assessor = load_obd_assessor()

    except Exception as e:
        st.error(f"Could not load the OBD-II anomaly model: {e}")
        st.stop()

    st.markdown("### 🔧 OBD-II Sensor Readings")
    st.caption(
        "Known faults are checked with Toyota threshold rules. "
        "The AI model (trained on healthy engines only) flags "
        "unusual patterns that no rule explains."
    )

    with st.form("obd_form"):

        vehicle_model = st.selectbox("Vehicle Model", VEHICLE_MODELS)

        col1, col2 = st.columns(2)

        with col1:
            obd_rpm = st.number_input(
                "Engine RPM",
                min_value=0,
                max_value=8000,
                value=1800,
                step=50,
                key="obd_rpm"
            )

            obd_load = st.number_input(
                "Engine Load (%)",
                min_value=0.0,
                max_value=100.0,
                value=45.0,
                step=1.0,
                key="obd_load"
            )

            obd_coolant = st.number_input(
                "Coolant Temperature (°C)",
                min_value=-40.0,
                max_value=150.0,
                value=88.0,
                step=1.0,
                key="obd_coolant"
            )

        with col2:
            vib_x = st.number_input(
                "Vibration X (g)",
                min_value=-2.0,
                max_value=2.0,
                value=0.05,
                step=0.01,
                format="%.4f"
            )

            vib_y = st.number_input(
                "Vibration Y (g)",
                min_value=-2.0,
                max_value=2.0,
                value=0.05,
                step=0.01,
                format="%.4f"
            )

            vib_z = st.number_input(
                "Vibration Z (g)",
                min_value=-2.0,
                max_value=2.0,
                value=0.05,
                step=0.01,
                format="%.4f"
            )

        obd_submitted = st.form_submit_button(
            "🔍 Check Vehicle",
            type="primary",
            use_container_width=True
        )

    if obd_submitted:

        readings = {
            "engine_rpm": obd_rpm,
            "engine_load": obd_load,
            "coolant_temp": obd_coolant,
            "vibration_x": vib_x,
            "vibration_y": vib_y,
            "vibration_z": vib_z,
            "vibration_magnitude": vibration_magnitude(vib_x, vib_y, vib_z),
        }

        try:
            result = assessor.assess(readings, vehicle_model)

            mitigation = get_mitigation_recommendation(
                result["fault"],
                sensor_readings=result["readings"]
            )

            if result["warming_up"]:
                mitigation["notes"].append(
                    "Engine is still warming up, so idle and "
                    "temperature rules were not applied."
                )
                if result["is_anomaly"] and not result["rule_findings"]:
                    mitigation["notes"].append(
                        "The AI score is high mainly because the engine "
                        "is cold. Check again once it is warm."
                    )

            st.divider()
            st.markdown("## 📊 Assessment Result")

            result_text = (
                f"{mitigation['display_name']} "
                f"(detected by: {result['source']})"
            )

            if result["fault"] == "Normal":
                st.success(result_text)
            else:
                st.warning(result_text)

            rule_col, ai_col = st.columns(2)

            with rule_col:
                st.markdown("### 📏 Rule Check")
                if result["rule_findings"]:
                    for finding in result["rule_findings"]:
                        st.markdown(
                            f"- **{finding['severity']}**: "
                            f"{finding['reason']}"
                        )
                else:
                    st.markdown("- No rule triggered")

            with ai_col:
                st.markdown("### 🤖 AI Anomaly Check")
                st.metric(
                    "Anomaly score",
                    f"{result['anomaly_score']:.2f}",
                    help=(
                        "Higher = more unusual. Readings above "
                        f"{result['anomaly_threshold']:.2f} are flagged."
                    )
                )
                if result["is_anomaly"]:
                    st.markdown("- Pattern is **unusual** for a healthy engine")
                else:
                    st.markdown("- Pattern looks like a healthy engine")

            st.markdown("### Submitted Sensor Values")

            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Engine RPM", f"{obd_rpm} RPM")
            v2.metric("Engine Load", f"{obd_load:.1f}%")
            v3.metric("Coolant", f"{obd_coolant:.0f} °C")
            v4.metric(
                "Vibration",
                f"{readings['vibration_magnitude']:.2f} g"
            )

            show_mitigation(mitigation)

        except Exception as e:
            st.error(
                f"An error occurred during assessment or mitigation: {e}"
            )


# Footer
st.divider()

st.caption(
    "AutoSense AI | AI-Based Hidden Fault Prediction and "
    "Mitigation System | Research Prototype"
)
