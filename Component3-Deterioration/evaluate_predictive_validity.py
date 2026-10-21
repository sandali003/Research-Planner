"""Component 3, step 4: does "accelerated deterioration" predict real future problems?

Ground truth comes from the next MOT of the same car: a 2023 test is joined to
the same vehicle's test 9-16 months later in 2024 (vehicle_id is kept across
years). If the contextual assessment works, cars it flags in 2023 should fail
more often in 2024.

Predictors of a 2024 major failure (proposal section 3.3 baselines):
  A  Age + mileage only        expected risk for the car's age, km, platform, fuel, engine
  B  Current condition only    the 2023 grade (failure rate per grade, learned on training cars)
  C  Proposed (contextual)     2023 grade placed among comparable cars: 1 - percentile
  D  Proposed + condition      logistic regression on the 2023 grade and C
Targets: overall (2024 grade Major or Dangerous) and per component (2024 major
defect in brakes, suspension, tyres, exhaust/emissions, steering).

No leakage: the expected-condition models are refitted on the 2023 training
vehicles only (same 80/20 vehicle split as train_expected_condition.py); every
number below is on held-out vehicles. Metrics: ROC-AUC, PR-AUC, precision /
recall / F1 of the flags (C's High / Slightly-high flags; A and B flag the same
number of cars, so the comparison is fair) and bootstrap 95% CIs of AUC gains.

Run:  python external_data/build_mot_toyota.py mot_2024 2024 --no-excel
      python evaluate_predictive_validity.py
"""

from pathlib import Path
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import OneHotEncoder

from contextual_assessment import HIGH_PERCENTILE, SLIGHT_PERCENTILE
from mot_condition import COMPONENT_GRADES, COMPONENTS, OVERALL_GRADES, add_grades
from ordinal_model import SEED, OrdinalBaseline
from train_expected_condition import clean

BASE_DIR = Path(__file__).resolve().parent
DATA = BASE_DIR / "external_data"
REPORT_FILE = BASE_DIR / "reports" / "predictive_validity_results.md"

FOLLOW_UP_DAYS = (270, 480)
BOOTSTRAP = 500


def load(year):
    return clean(add_grades(pd.read_csv(DATA / f"mot_toyota_{year}.csv", parse_dates=["test_date"])))


def follow_up_pairs(d23, d24):
    """Each car's last 2023 test joined to its first 2024 test 9-16 months later."""
    first = d23.sort_values("test_date").groupby("vehicle_id").tail(1)
    nxt = d24.sort_values("test_date")
    pairs = first.merge(nxt, on="vehicle_id", suffixes=("", "_next"))
    gap = (pairs["test_date_next"] - pairs["test_date"]).dt.days
    pairs = pairs[gap.between(*FOLLOW_UP_DAYS)]
    return pairs.groupby("vehicle_id").head(1).reset_index(drop=True)


def percentile(probs, levels, grades):
    """Share of comparable cars in a worse condition than each observed grade (mid-rank)."""
    idx = np.searchsorted(levels, grades)
    rows = np.arange(len(grades))
    cum = np.cumsum(probs, axis=1)
    below = np.where(idx > 0, cum[rows, np.maximum(idx - 1, 0)], 0.0)
    return below + 0.5 * probs[rows, idx]


def scores(model, levels, frame, grade_col, bad_levels):
    """Scores A (expected risk) and C (1 - percentile) for one target."""
    probs = model.predict_proba(frame)
    expected_risk = probs[:, [levels.index(k) for k in bad_levels]].sum(axis=1)
    return expected_risk, 1 - percentile(probs, levels, frame[grade_col].values)


def flag_metrics(y, flag):
    return {"flagged": float(flag.mean()), "precision": precision_score(y, flag, zero_division=0),
            "recall": recall_score(y, flag, zero_division=0), "f1": f1_score(y, flag, zero_division=0)}


def top_k(score, k):
    """Flag the k highest scores (ties broken at random so the count is exact)."""
    order = np.lexsort((np.random.default_rng(SEED).random(len(score)), -score))
    flag = np.zeros(len(score), bool)
    flag[order[:k]] = True
    return flag


def bootstrap_gain(y, better, base, rng):
    gains = []
    n = len(y)
    for _ in range(BOOTSTRAP):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        gains.append(roc_auc_score(y[i], better[i]) - roc_auc_score(y[i], base[i]))
    return np.percentile(gains, [2.5, 97.5])


def evaluate_target(name, grade_col, levels, bad_levels, train23, train_pairs, test_pairs, rng):
    model = OrdinalBaseline(levels).fit(train23, train23[grade_col])
    next_col = f"{grade_col}_next"

    def prepared(pairs):
        y = pairs[next_col].isin(bad_levels).astype(int).values
        a, c = scores(model, levels, pairs, grade_col, bad_levels)
        return y, a, c

    y_tr, a_tr, c_tr = prepared(train_pairs)
    y_te, a_te, c_te = prepared(test_pairs)

    # B: failure rate per 2023 grade, learned on training cars
    rate = pd.Series(y_tr).groupby(train_pairs[grade_col].values).mean()
    b_te = test_pairs[grade_col].map(rate).fillna(y_tr.mean()).values

    # D: 2023 grade (one-hot) + contextual score
    enc = OneHotEncoder(handle_unknown="ignore").fit(train_pairs[[grade_col]])

    def design(pairs, c):
        return np.hstack([enc.transform(pairs[[grade_col]]).toarray(), np.log(c + 1e-3)[:, None]])

    lr = LogisticRegression(max_iter=1000).fit(design(train_pairs, c_tr), y_tr)
    d_te = lr.predict_proba(design(test_pairs, c_te))[:, 1]

    predictors = {"A Age + mileage only": a_te, "B Current condition only": b_te,
                  "C Proposed (contextual)": c_te, "D Proposed + condition": d_te}
    rows = [{"Target": name, "Predictor": p, "n": len(y_te), "positive rate": y_te.mean(),
             "ROC-AUC": roc_auc_score(y_te, s), "PR-AUC": average_precision_score(y_te, s)}
            for p, s in predictors.items()]

    # Flags: C's statistical flags vs A and B flagging the same number of cars
    flags = []
    pct = 1 - c_te
    for label, cut in (("High (worst 10%)", HIGH_PERCENTILE), ("High + Slightly high (worst 25%)", SLIGHT_PERCENTILE)):
        c_flag = pct <= cut
        k = int(c_flag.sum())
        for p, flag in (("C Proposed (contextual)", c_flag), ("A Age + mileage only", top_k(a_te, k)),
                        ("B Current condition only", top_k(b_te, k))):
            flags.append({"Target": name, "Flag": label, "Predictor": p, **flag_metrics(y_te, flag)})

    gains = {f"{p} vs B": bootstrap_gain(y_te, predictors[p], b_te, rng)
             for p in ("C Proposed (contextual)", "D Proposed + condition")}
    return rows, flags, gains


def markdown(df, pct_cols=(), dp=3):
    def cell(col, v):
        if isinstance(v, float):
            return f"{v * 100:.1f}%" if col in pct_cols else f"{v:.{dp}f}"
        return str(v)
    lines = ["| " + " | ".join(df.columns) + " |", "|---" * len(df.columns) + "|"]
    lines += ["| " + " | ".join(cell(c, v) for c, v in zip(df.columns, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    started = time.perf_counter()
    d23, d24 = load(2023), load(2024)
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    train_idx, test_idx = next(split.split(d23, groups=d23["vehicle_id"]))
    train23 = d23.iloc[train_idx]
    test_vehicles = set(d23.iloc[test_idx]["vehicle_id"])

    pairs = follow_up_pairs(d23, d24)
    is_test = pairs["vehicle_id"].isin(test_vehicles)
    train_pairs, test_pairs = pairs[~is_test].reset_index(drop=True), pairs[is_test].reset_index(drop=True)
    print(f"2023 tests {len(d23):,} | 2024 tests {len(d24):,} | cars with a follow-up {len(pairs):,} "
          f"(test {len(test_pairs):,})")

    rng = np.random.default_rng(SEED)
    targets = [("Overall", "grade", sorted(OVERALL_GRADES), [1, 2])]
    targets += [(c.replace("_", " ").title(), f"grade_{c}", sorted(COMPONENT_GRADES), [1]) for c in COMPONENTS]

    rows, flags, gains = [], [], []
    for name, col, levels, bad in targets:
        r, f, g = evaluate_target(name, col, levels, bad, train23, train_pairs, test_pairs, rng)
        rows += r
        flags += f
        gains += [{"Target": name, "Comparison": k, "AUC gain 95% CI": f"{lo:+.3f} to {hi:+.3f}"} for k, (lo, hi) in g.items()]
        print(pd.DataFrame(r)[["Target", "Predictor", "ROC-AUC", "PR-AUC"]].round(3).to_string(index=False), flush=True)

    results, flag_table, gain_table = pd.DataFrame(rows), pd.DataFrame(flags), pd.DataFrame(gains)
    results.to_csv(BASE_DIR / "reports" / "predictive_validity_results.csv", index=False)
    flag_table.to_csv(BASE_DIR / "reports" / "predictive_validity_flags.csv", index=False)

    report = [
        "# Predictive validity of the contextual assessment (Component 3, step 4)", "",
        f"2023 MOT tests joined to the same car's next test 9-16 months later in 2024. "
        f"{len(pairs):,} cars with a follow-up; results on {len(test_pairs):,} held-out cars. "
        "Outcome: a major (or dangerous) defect at the 2024 test, overall or in the component.", "",
        "## Ranking (higher is better)", "",
        markdown(results, pct_cols=("positive rate",)), "",
        "## Bootstrap 95% CI of the ROC-AUC gain over B (current condition only)", "",
        markdown(gain_table), "",
        "## Flags: precision / recall / F1 (A and B flag the same number of cars as C)", "",
        markdown(flag_table, pct_cols=("flagged", "precision", "recall", "f1")), "",
    ]
    REPORT_FILE.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Done in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
