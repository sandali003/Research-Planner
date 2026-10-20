"""Vehicle health assessment: sensor readings -> component scores -> overall score -> condition -> XAI.

Pipeline
  1. Component scoring (0-100, transparent rules on OBD-II + external sensor readings)
       thermal    <- DS18B20 temperature sensor
       electrical <- battery voltage sensor
       vibration  <- MPU6050 vibration RMS / peak
       obd        <- OBD-II diagnostic trouble codes x engine operation (RPM, engine load)
  2. Overall score (0-100) predicted by an ML model trained on the 4 component scores.
  3. Condition: Good / Fair / Poor / Critical from the overall score.
  4. XAI: SHAP values on the component scores + plain-language reasons from the raw readings.

Train:  python health_assessment.py
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "malindu" / "AutoSense_Fabricated_Toyota_External_Sensor_Dataset_10000.csv"
MODEL_FILE = ROOT / "models" / "health_overall.joblib"
SUMMARY_FILE = ROOT / "models" / "health_summary.json"

COMPONENTS = ["thermal", "electrical", "vibration", "obd"]
LABELS = {"thermal": "Engine temperature", "electrical": "Battery / electrical",
          "vibration": "Vibration", "obd": "OBD-II (fault codes, RPM, load)"}

# Engine operation limits (OBD-II live data). Lugging = high load at low RPM.
RPM_NORMAL = (600, 4500)
LUG_RPM, LUG_LOAD = 1500, 70

# Condition bands on the overall score. Good/Fair/Poor edges match the dataset's own classes;
# the Poor/Critical split at 50 is our choice (the dataset has no Critical class).
BANDS = [(80, "Good"), (60, "Fair"), (50, "Poor"), (0, "Critical")]

DTC_INFO = {
    "P0562": "system voltage low (charging / battery)",
    "P0300": "random / multiple cylinder misfire",
    "P0117": "coolant temperature sensor circuit low",
    "P0171": "fuel system too lean (bank 1)",
    "P0420": "catalyst efficiency below threshold",
    "P0101": "mass air flow sensor range / performance",
}


# ---------------------------------------------------------------- 1. component scores
def _ramp(x, good_lo, good_hi, zero_lo, zero_hi):
    """100 inside [good_lo, good_hi], falling linearly to 0 at zero_lo / zero_hi."""
    if x < good_lo:
        return float(np.clip(100 * (x - zero_lo) / (good_lo - zero_lo), 0, 100))
    if x > good_hi:
        return float(np.clip(100 * (zero_hi - x) / (zero_hi - good_hi), 0, 100))
    return 100.0


def parse_dtcs(codes):
    if not codes or (isinstance(codes, float) and np.isnan(codes)):
        return []
    return [c.strip().upper() for c in str(codes).replace(",", ";").split(";") if c.strip()]


def _missing(x):
    return x is None or (isinstance(x, float) and np.isnan(x))


def engine_operation(r):
    """0-100 from OBD-II RPM and load; 100 when they are not provided (no evidence of a problem)."""
    rpm, load = r.get("engine_rpm"), r.get("engine_load_pct")
    if _missing(rpm):
        return 100.0
    score = _ramp(rpm, *RPM_NORMAL, 300, 6500)
    if not _missing(load) and rpm < LUG_RPM:
        score = min(score, _ramp(load, 0, LUG_LOAD, -1, 100))
    return score


def component_scores(r):
    """r: dict with ds18b20_temp_c, battery_voltage_v, vibration_rms_g, vibration_peak_g, dtc_codes
    and optionally engine_rpm, engine_load_pct."""
    thermal = _ramp(r["ds18b20_temp_c"], 70, 100, 40, 125)
    electrical = _ramp(r["battery_voltage_v"], 13.4, 14.6, 11.0, 15.6)
    vib = 0.6 * _ramp(r["vibration_rms_g"], 0, 0.04, -1, 0.20) + 0.4 * _ramp(r["vibration_peak_g"], 0, 0.20, -1, 1.0)
    dtc = max(0.0, 100 - 30 * len(parse_dtcs(r.get("dtc_codes"))))
    obd = dtc * engine_operation(r) / 100
    return {"thermal": thermal, "electrical": electrical, "vibration": vib, "obd": obd}


def condition_of(score):
    return next(name for edge, name in BANDS if score >= edge)


# ---------------------------------------------------------------- 2. train overall model
def _frame(df):
    rows = [component_scores({"ds18b20_temp_c": t, "battery_voltage_v": v, "vibration_rms_g": a,
                              "vibration_peak_g": p, "dtc_codes": c, "engine_rpm": rpm, "engine_load_pct": load})
            for t, v, a, p, c, rpm, load in zip(df.ds18b20_temp_c, df.battery_voltage_v, df.vibration_rms_g,
                                                df.vibration_peak_g, df.dtc_codes_simulated,
                                                df.engine_rpm, df.engine_load_pct)]
    return pd.DataFrame(rows)[COMPONENTS]


def train():
    df = pd.read_csv(DATA_FILE)
    X, y = _frame(df), df.health_score_0_100_simulated
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    # monotonic: a better component score can never lower the overall score
    model = HistGradientBoostingRegressor(monotonic_cst=[1] * len(COMPONENTS), random_state=42).fit(Xtr, ytr)
    pred = model.predict(Xte)

    cond_true = yte.map(condition_of)
    cond_pred = pd.Series(pred, index=yte.index).map(condition_of)
    baseline = LinearBaseline(Xtr, ytr).predict(Xte)
    summary = {
        "rows": len(df), "r2": round(r2_score(yte, pred), 4), "mae": round(mean_absolute_error(yte, pred), 3),
        "linear_baseline_r2": round(r2_score(yte, baseline), 4),
        "condition_accuracy": round(float((cond_true == cond_pred).mean()), 4),
        "condition_counts_true": cond_true.value_counts().to_dict(),
        "majority_class_accuracy": round(float(cond_true.value_counts(normalize=True).iloc[0]), 4),
        "condition_recall": {k: round(float((cond_pred[cond_true == k] == k).mean()), 3) for k in cond_true.unique()},
        "note": "Labels are rule-based simulated scores, not mechanic-verified.",
    }
    background = Xtr.sample(200, random_state=0)
    MODEL_FILE.parent.mkdir(exist_ok=True)
    joblib.dump({"model": model, "background": background}, MODEL_FILE)
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("\nConfusion (rows=true, cols=pred):")
    print(pd.crosstab(cond_true, cond_pred))
    return summary


class LinearBaseline:
    def __init__(self, X, y):
        from sklearn.linear_model import LinearRegression
        self.m = LinearRegression().fit(X, y)

    def predict(self, X):
        return self.m.predict(X)


# ---------------------------------------------------------------- 3 + 4. assess & explain
_cache = {}


def _load():
    if not _cache:
        bundle = joblib.load(MODEL_FILE)
        model, bg = bundle["model"], bundle["background"]
        _cache.update(model=model, explainer=shap.Explainer(model.predict, shap.maskers.Independent(bg, max_samples=len(bg)),
                                                   algorithm="exact"),
                      base=float(model.predict(bg).mean()))
    return _cache


def _reasons(r, comps):
    """Plain-language evidence behind each component score, from the raw readings."""
    t, v, rms, pk = r["ds18b20_temp_c"], r["battery_voltage_v"], r["vibration_rms_g"], r["vibration_peak_g"]
    dtcs = parse_dtcs(r.get("dtc_codes"))
    out = {}
    out["thermal"] = (f"temperature {t:.1f} °C is " + ("above" if t > 100 else "below" if t < 70 else "within")
                      + " the normal 70-100 °C range")
    out["electrical"] = (f"voltage {v:.2f} V is " + ("above" if v > 14.6 else "below" if v < 13.4 else "within")
                         + " the normal running range 13.4-14.6 V")
    out["vibration"] = (f"vibration RMS {rms:.3f} g (normal ≤ 0.04) and peak {pk:.3f} g (normal ≤ 0.20)")
    out["obd"] = ("no fault codes stored" if not dtcs else
                  f"{len(dtcs)} fault code(s): " + "; ".join(f"{c} {DTC_INFO.get(c, 'see service manual')}" for c in dtcs))
    out["obd"] += "; " + _engine_reason(r)
    return out


def _engine_reason(r):
    rpm, load = r.get("engine_rpm"), r.get("engine_load_pct")
    if _missing(rpm):
        return "engine RPM not provided"
    lo, hi = RPM_NORMAL
    if rpm < lo:
        return f"engine RPM {rpm:.0f} is below {lo} (unstable / rough idle)"
    if rpm > hi:
        return f"engine RPM {rpm:.0f} is above {hi} (over-revving)"
    if not _missing(load) and rpm < LUG_RPM and load > LUG_LOAD:
        return f"engine load {load:.0f}% at only {rpm:.0f} RPM (engine lugging / strain)"
    load_txt = "" if _missing(load) else f", load {load:.0f}%"
    return f"engine RPM {rpm:.0f}{load_txt} is normal"


def assess(reading):
    """reading: dict(ds18b20_temp_c, battery_voltage_v, vibration_rms_g, vibration_peak_g, dtc_codes[, engine_rpm, engine_load_pct])"""
    c = _load()
    reading = {**reading, "engine_rpm": reading.get("engine_rpm"), "engine_load_pct": reading.get("engine_load_pct")}
    comps = component_scores(reading)
    X = pd.DataFrame([comps])[COMPONENTS]
    overall = float(np.clip(c["model"].predict(X)[0], 0, 100))
    condition = condition_of(overall)
    sv = c["explainer"](X).values[0]
    reasons = _reasons(reading, comps)

    factors = sorted(({"component": k, "label": LABELS[k], "score": round(comps[k], 1),
                       "impact": round(float(s), 2), "reason": reasons[k]} for k, s in zip(COMPONENTS, sv)),
                     key=lambda f: f["impact"])
    for f in factors:
        f["status"] = "Normal" if f["score"] >= 80 else "Watch" if f["score"] >= 60 else "Abnormal"

    worst = factors[0]
    fixed = comps | {worst["component"]: 100.0}
    potential = float(c["model"].predict(pd.DataFrame([fixed])[COMPONENTS])[0])

    lines = [f"Overall health score {overall:.1f}/100 → {condition.upper()} "
             f"(average vehicle scores {c['base']:.1f})."]
    drags = [f for f in factors if f["impact"] < -0.5]
    if drags:
        for f in drags:
            lines.append(f"• {f['label']} (score {f['score']:.0f}) lowered the score by {-f['impact']:.1f} points: {f['reason']}.")
        lines.append(f"If {worst['label'].lower()} were fully healthy, the score would rise to about "
                     f"{potential:.1f} ({condition_of(potential)}).")
    else:
        lines.append("All components are at or near normal; nothing is pulling the score down.")
    return {"overall": round(overall, 1), "condition": condition, "base": round(c["base"], 1),
            "components": {k: round(v, 1) for k, v in comps.items()}, "factors": factors,
            "potential": round(potential, 1), "explanation": "\n".join(lines)}


if __name__ == "__main__":
    train()
    demo = dict(ds18b20_temp_c=108, battery_voltage_v=12.4, vibration_rms_g=0.12, vibration_peak_g=0.6,
                dtc_codes="P0300;P0562", engine_rpm=2200, engine_load_pct=55)
    print("\n--- demo assessment ---")
    print(assess(demo)["explanation"])
