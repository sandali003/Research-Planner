"""Web UI for the vehicle health assessment. Run: python assessment_app.py  ->  http://127.0.0.1:5001"""
from flask import Flask, render_template_string, request

from health_assessment import COMPONENTS, DTC_INFO, assess

app = Flask(__name__)

FIELDS = [  # name, label, default, min, max, step
    ("engine_rpm", "Engine RPM (OBD-II)", 1800, 500, 7000, 10),
    ("engine_load_pct", "Engine load % (OBD-II)", 40, 0, 100, 0.1),
    ("ds18b20_temp_c", "Engine temperature °C (DS18B20)", 92, 40, 140, 0.1),
    ("battery_voltage_v", "Battery voltage V", 14.0, 9, 16, 0.01),
    ("vibration_rms_g", "Vibration RMS g (MPU6050)", 0.03, 0, 1, 0.001),
    ("vibration_peak_g", "Vibration peak g (MPU6050)", 0.12, 0, 3, 0.001),
]
PRESETS = {
    "Healthy car": dict(engine_rpm=1800, engine_load_pct=40, ds18b20_temp_c=90, battery_voltage_v=14.1,
                        vibration_rms_g=0.03, vibration_peak_g=0.12, dtc=[]),
    "Worn engine": dict(engine_rpm=2200, engine_load_pct=55, ds18b20_temp_c=104, battery_voltage_v=13.2,
                        vibration_rms_g=0.09, vibration_peak_g=0.45, dtc=["P0300", "P0171"]),
    "Failing car": dict(engine_rpm=2400, engine_load_pct=70, ds18b20_temp_c=112, battery_voltage_v=11.9,
                        vibration_rms_g=0.18, vibration_peak_g=0.9, dtc=["P0300", "P0562", "P0117"]),
}
COLORS = {"Good": "#16a34a", "Fair": "#ca8a04", "Poor": "#ea580c", "Critical": "#dc2626",
          "Normal": "#16a34a", "Watch": "#ca8a04", "Abnormal": "#dc2626"}

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>Vehicle Health Assessment</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#f4f6f8;color:#1c2330}
header{background:#1c2b4a;color:#fff;padding:16px 24px}
main{max-width:1000px;margin:20px auto;padding:0 24px;display:grid;grid-template-columns:340px 1fr;gap:16px}
@media(max-width:800px){main{grid-template-columns:1fr}}
.card{background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 3px #0001;margin-bottom:16px}
label{font-size:12px;color:#556;display:block;margin:10px 0 3px}
input[type=number]{width:100%;padding:7px;border:1px solid #ccd;border-radius:6px;box-sizing:border-box}
.dtc{display:block;font-size:13px;margin:4px 0}
button{padding:10px 20px;background:#2563eb;color:#fff;border:0;border-radius:6px;font-size:15px;cursor:pointer;margin-top:14px}
.pre a{display:inline-block;margin:2px 4px 2px 0;padding:4px 10px;background:#eef1f6;border-radius:12px;font-size:12px;color:#1c2b4a;text-decoration:none}
.badge{display:inline-block;color:#fff;padding:6px 18px;border-radius:20px;font-weight:700;font-size:22px}
.score{font-size:46px;font-weight:800;margin:6px 0}
.row{display:flex;align-items:center;gap:8px;font-size:13px;margin:7px 0}
.row .n{width:150px}.row .t{flex:1;background:#e5e9f0;border-radius:5px;height:12px;position:relative}
.row .f{height:12px;border-radius:5px}
.div .t{background:#e5e9f0}.div .mid{position:absolute;left:50%;top:-2px;width:1px;height:16px;background:#667}
.muted{color:#667;font-size:13px}.why{white-space:pre-line;line-height:1.55;font-size:14px}
.tag{font-size:11px;color:#fff;border-radius:4px;padding:1px 6px}
</style></head><body>
<header><h2 style="margin:0">AI Vehicle Health Assessment</h2>
<div class="muted" style="color:#b9c4dd">OBD-II + external sensors → component scores → overall score → condition → explanation</div></header>
<main>
<form method="post" class="card"><b>Sensor readings</b>
<div class="pre">Presets: {% for p in presets %}<a href="/?preset={{p}}">{{p}}</a>{% endfor %}</div>
{% for n,l,d,lo,hi,st in fields %}<label>{{l}}</label>
<input type="number" name="{{n}}" value="{{vals[n]}}" min="{{lo}}" max="{{hi}}" step="{{st}}" required>{% endfor %}
<label>OBD-II fault codes (DTC)</label>
{% for c,desc in dtcs.items() %}<label class="dtc"><input type="checkbox" name="dtc" value="{{c}}" {{'checked' if c in vals.dtc}}> {{c}} - {{desc}}</label>{% endfor %}
<button>Assess vehicle</button></form>
<div>
{% if r %}
<div class="card"><div class="muted">Vehicle condition</div>
<span class="badge" style="background:{{colors[r.condition]}}">{{r.condition}}</span>
<div class="score">{{r.overall}}<span style="font-size:20px;color:#889"> / 100</span></div>
<div class="muted">Good ≥ 80 · Fair 60-80 · Poor 50-60 · Critical &lt; 50 · average vehicle {{r.base}}</div></div>
<div class="card"><b>Component scores</b>
{% for f in r.factors|sort(attribute='component') %}<div class="row"><span class="n">{{f.label}}</span>
<div class="t"><div class="f" style="width:{{f.score}}%;background:{{colors[f.status]}}"></div></div>
<span style="width:34px">{{'%.0f'|format(f.score)}}</span><span class="tag" style="background:{{colors[f.status]}}">{{f.status}}</span></div>{% endfor %}</div>
<div class="card"><b>Why this condition? (SHAP: points added / removed vs. average vehicle)</b>
{% for f in r.factors %}<div class="row div"><span class="n">{{f.label}}</span>
<div class="t"><div class="mid"></div>
<div class="f" style="position:absolute;height:12px;background:{{'#16a34a' if f.impact>=0 else '#dc2626'}};
{% if f.impact>=0 %}left:50%;{% else %}right:50%;{% endif %}width:{{ [f.impact|abs*2.5, 50]|min }}%"></div></div>
<span style="width:52px;text-align:right">{{'%+.1f'|format(f.impact)}}</span></div>{% endfor %}
<hr style="border:0;border-top:1px solid #e5e9f0;margin:14px 0"><div class="why">{{r.explanation}}</div></div>
{% else %}<div class="card muted">Enter readings (or pick a preset) and press <b>Assess vehicle</b>.</div>{% endif %}
</div></main></body></html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    vals = {n: d for n, _, d, *_ in FIELDS} | {"dtc": []}
    result = None
    if request.method == "POST":
        vals = {n: float(request.form[n]) for n, *_ in FIELDS} | {"dtc": request.form.getlist("dtc")}
    elif request.args.get("preset") in PRESETS:
        vals = PRESETS[request.args["preset"]]
    if request.method == "POST" or request.args.get("preset"):
        reading = {k: v for k, v in vals.items() if k != "dtc"} | {"dtc_codes": ";".join(vals["dtc"])}
        result = assess(reading)
    return render_template_string(PAGE, fields=FIELDS, vals=vals, dtcs=DTC_INFO, r=result,
                                  presets=list(PRESETS), colors=COLORS)


if __name__ == "__main__":
    app.run(port=5001)
