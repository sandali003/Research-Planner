# AI Vehicle Health Assessment

Component of the research project: takes OBD-II data and external sensor readings
(temperature, vibration, voltage), scores each component, predicts an overall vehicle
health score, gives a condition (Good / Fair / Poor / Critical) and explains why with XAI (SHAP).

## Pipeline (`health_assessment.py`)
1. Component scores (0-100): engine temperature, battery/electrical, vibration, OBD-II
   (fault-code score x engine-operation factor from RPM and load: RPM normal 600-4500,
   lugging = load > 70% below 1500 RPM; no penalty when RPM/load are not provided)
2. Overall score: Gradient Boosting model (monotonic) trained on the component scores
3. Condition: Good >= 80, Fair 60-80, Poor 50-60, Critical < 50
4. XAI: SHAP contributions per component + plain-language reasons from raw readings

Test set: R2 0.907, MAE 2.6 points, condition accuracy 94.3%.
Labels in the datasets are rule-based **simulated** scores (not mechanic-verified).

## Run
```
pip install -r requirements.txt
python health_assessment.py     # train overall-score model + demo explanation
python assessment_app.py        # web UI -> http://127.0.0.1:5001
python train.py                 # baseline models for all 6 datasets in ./malindu
python app.py                   # demo UI for those 6 models -> http://127.0.0.1:5000
```

## Files
- `malindu/` - datasets (synthetic / simulated)
- `models/` - trained models (`.joblib`) and metrics (`summary.json`, `health_summary.json`)

> models/engine_data.joblib (154 MB) is not committed because of GitHub's 100 MB limit; run python train.py to regenerate it.
