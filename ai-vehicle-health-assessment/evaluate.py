"""Honest evaluation of every dataset: grouped k-fold CV, trivial baselines, per-class recall,
and a shallow-tree check that reveals labels which are (near-)deterministic rules on the inputs.

Run: python evaluate.py   -> prints results and writes EVALUATION.md
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import confusion_matrix, f1_score, mean_absolute_error, r2_score, recall_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from train import DATA, DATASETS

warnings.filterwarnings("ignore")
GROUP_COL = {"external_sensor": "vehicle_id", "battery": "vehicle_id", "inspection": "vehicle_id"}
SEED = 42


def make_pipe(model, cat):
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), cat)], remainder="passthrough")
    return Pipeline([("pre", pre), ("m", model)])


def splitter(task, groups, n=5):
    if groups is not None and groups.nunique() >= n:
        return GroupKFold(n_splits=n), groups
    if task == "clf":
        return StratifiedKFold(n, shuffle=True, random_state=SEED), None
    return KFold(n, shuffle=True, random_state=SEED), None


def evaluate(name, file, target, task, drop):
    raw = pd.read_csv(DATA / file)
    raw = raw.dropna(subset=[target])
    gcol = GROUP_COL.get(name)
    groups = raw[gcol] if gcol in raw else None
    df = raw.drop(columns=drop)
    X, y = df.drop(columns=[target]), df[target]
    X = X.loc[:, X.nunique() > 1]
    cat = X.select_dtypes(exclude="number").columns.tolist()
    cv, g = splitter(task, groups)
    cv_kind = type(cv).__name__

    models = {
        "HistGB": (HistGradientBoostingClassifier(random_state=SEED) if task == "clf"
                   else HistGradientBoostingRegressor(random_state=SEED)),
        "Baseline(majority/mean)": DummyClassifier() if task == "clf" else DummyRegressor(),
        "ShallowTree(depth3)": (DecisionTreeClassifier(max_depth=3, random_state=SEED) if task == "clf"
                                else DecisionTreeRegressor(max_depth=3, random_state=SEED)),
    }
    res = {}
    classes = sorted(y.unique().astype(str)) if task == "clf" else None
    for mname, model in models.items():
        scores, preds_all, true_all = [], [], []
        for tr, te in cv.split(X, y, g):
            pipe = make_pipe(model, cat).fit(X.iloc[tr], y.iloc[tr])
            p = pipe.predict(X.iloc[te])
            if task == "clf":
                scores.append(f1_score(y.iloc[te], p, average="macro"))
                preds_all += list(p.astype(str)); true_all += list(y.iloc[te].astype(str))
            else:
                scores.append(r2_score(y.iloc[te], p))
        res[mname] = (np.mean(scores), np.std(scores), true_all, preds_all)

    out = [f"### {name}  ({len(df)} rows, target `{target}`, {cv_kind} 5-fold)",
           f"Metric: {'macro-F1' if task == 'clf' else 'R²'} (mean ± std over folds)", ""]
    out += ["| model | score |", "|---|---|"]
    for m, (mu, sd, *_ ) in res.items():
        out.append(f"| {m} | {mu:.3f} ± {sd:.3f} |")
    if task == "clf":
        t, p = res["HistGB"][2], res["HistGB"][3]
        rec = recall_score(t, p, average=None, labels=classes, zero_division=0)
        out += ["", "Per-class recall (HistGB, pooled folds): " +
                ", ".join(f"{c}={r:.2f} (n={t.count(c)})" for c, r in zip(classes, rec))]
        cm = pd.DataFrame(confusion_matrix(t, p, labels=classes), index=classes, columns=classes)
        out += ["", "Confusion matrix (rows=true, cols=pred):", "```", cm.to_string(), "```"]
    gb, base, tree = res["HistGB"][0], res["Baseline(majority/mean)"][0], res["ShallowTree(depth3)"][0]
    flags = []
    if gb - base < 0.05:
        flags.append("NO SIGNAL: barely beats the trivial baseline.")
    if tree >= 0.95 * gb and gb > 0.9:
        flags.append("RULE-LIKE LABEL: a depth-3 tree matches the full model, so the label is a simple "
                     "deterministic function of a few inputs (model learns the rule, not real-world faults).")
    if gb >= 0.99:
        flags.append("NEAR-PERFECT SCORE: suspicious / trivially separable.")
    out += ["", "**Flags:** " + (" ".join(flags) if flags else "none"), ""]
    return "\n".join(out)


if __name__ == "__main__":
    parts = ["# Evaluation report (grouped/stratified 5-fold CV)\n",
             "All datasets are synthetic or rule-labelled; scores measure recovery of the label rule, "
             "not real-vehicle accuracy.\n"]
    for n, cfg in DATASETS.items():
        print("evaluating", n, flush=True)
        parts.append(evaluate(n, *cfg))
    report = "\n".join(parts)
    Path(__file__).with_name("EVALUATION.md").write_text(report, encoding="utf-8")
    print(report)
