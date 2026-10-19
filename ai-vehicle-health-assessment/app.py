"""Demo web app: pick a dataset/model, enter values, get a prediction. Run: python app.py"""
import json
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, render_template_string, request

from train import DATA, DATASETS, OUT

app = Flask(__name__)
SUMMARY = json.loads((OUT / "summary.json").read_text())

TITLES = {
    "inspection": "Vehicle Inspection (health class)",
    "external_sensor": "External Sensors (health class)",
    "battery": "Battery / Charging (fault type)",
    "petrol_engine": "Petrol Engine (health score)",
    "engine_data": "Engine Data (condition 0/1)",
    "engine_fault": "Engine Fault Detection (condition 0/1/2)",
}

# Per dataset: model + field specs (numeric -> min/max/median, categorical -> options)
MODELS = {}
for name, (file, target, task, drop) in DATASETS.items():
    df = pd.read_csv(DATA / file).drop(columns=drop)
    fields = []
    for col in SUMMARY[name]["features"]:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            fields.append({"name": col, "kind": "num", "min": float(s.min()), "max": float(s.max()),
                           "default": round(float(s.median()), 4)})
        else:
            opts = sorted(s.dropna().astype(str).unique())
            fields.append({"name": col, "kind": "cat", "options": opts, "default": s.mode()[0]})
    MODELS[name] = {"model": joblib.load(OUT / f"{name}.joblib"), "fields": fields,
                    "task": task, "target": target, "info": SUMMARY[name]}

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>Vehicle Health Assessment</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#f4f6f8;color:#1c2330}
header{background:#1c2b4a;color:#fff;padding:16px 24px}
nav{display:flex;flex-wrap:wrap;gap:6px;padding:12px 24px;background:#fff;border-bottom:1px solid #dde}
nav a{padding:8px 14px;border-radius:6px;text-decoration:none;color:#1c2b4a;background:#eef1f6;font-size:14px}
nav a.on{background:#1c2b4a;color:#fff}
main{max-width:960px;margin:20px auto;padding:0 24px}
.card{background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 3px #0001;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
label{font-size:12px;color:#556;display:block;margin-bottom:3px}
input,select{width:100%;padding:7px;border:1px solid #ccd;border-radius:6px;box-sizing:border-box}
button{margin-top:16px;padding:10px 24px;background:#2563eb;color:#fff;border:0;border-radius:6px;font-size:15px;cursor:pointer}
.res{font-size:26px;font-weight:700;margin:4px 0 12px}
.bar{display:flex;align-items:center;gap:8px;font-size:13px;margin:4px 0}
.bar div.f{height:10px;background:#2563eb;border-radius:5px}
.bar div.t{flex:1;background:#e5e9f0;border-radius:5px}
.muted{color:#667;font-size:13px}
</style></head><body>
<header><h2 style="margin:0">Vehicle Health Assessment - Demo</h2></header>
<nav>{% for k,t in titles.items() %}<a href="/?d={{k}}" class="{{'on' if k==cur}}">{{t}}</a>{% endfor %}</nav>
<main>
<div class="card"><b>{{titles[cur]}}</b>
<div class="muted">Model: {{m.info.model}} | trained on {{m.info.rows}} rows | target: {{m.target}} |
{{'macro-F1' if m.task=='clf' else 'R2'}} on test set: {{m.info.score}}</div></div>
{% if result is not none %}
<div class="card"><div class="muted">Prediction</div>
<div class="res">{{result}}</div>
{% for c,p in probs %}<div class="bar"><span style="width:170px">{{c}}</span>
<div class="t"><div class="f" style="width:{{p*100}}%"></div></div><span>{{'%.1f'|format(p*100)}}%</span></div>{% endfor %}
</div>{% endif %}
<form method="post" class="card"><input type="hidden" name="d" value="{{cur}}">
<div class="grid">
{% for f in m.fields %}<div><label>{{f.name}}{% if f.kind=='num' %} ({{f.min}} - {{f.max}}){% endif %}</label>
{% if f.kind=='num' %}<input type="number" step="any" name="{{f.name}}" value="{{vals.get(f.name, f.default)}}" required>
{% else %}<select name="{{f.name}}">{% for o in f.options %}<option {{'selected' if o==vals.get(f.name, f.default)}}>{{o}}</option>{% endfor %}</select>{% endif %}
</div>{% endfor %}</div>
<button>Predict</button></form>
</main></body></html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    cur = (request.values.get("d") or "inspection")
    if cur not in MODELS:
        cur = "inspection"
    m = MODELS[cur]
    vals, result, probs = {}, None, []
    if request.method == "POST":
        vals = {f["name"]: request.form[f["name"]] for f in m["fields"]}
        row = {f["name"]: (float(vals[f["name"]]) if f["kind"] == "num" else vals[f["name"]])
               for f in m["fields"]}
        X = pd.DataFrame([row])
        pipe = m["model"]
        pred = pipe.predict(X)[0]
        if m["task"] == "clf":
            result = str(pred)
            probs = sorted(zip(map(str, pipe.classes_), pipe.predict_proba(X)[0]), key=lambda t: -t[1])
        else:
            result = f"{pred:.3f}"
    return render_template_string(PAGE, titles=TITLES, cur=cur, m=m, vals=vals, result=result, probs=probs)


if __name__ == "__main__":
    app.run(debug=False, port=5000)
