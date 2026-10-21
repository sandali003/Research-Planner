"""Probability models for condition grades (used by train_expected_condition.py).

Kept in their own module so the saved model can be loaded by the API and
other scripts (pickle stores the module path of these classes).
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

CATEGORICAL = ["platform", "fuel_type"]
NUMERIC = ["age_years", "odometer_km", "engine_cc"]
MONOTONIC = {"age_years": 1, "odometer_km": 1}  # more age / km -> higher chance of a worse grade
SEED = 0


class OrdinalBaseline:
    """P(grade <= k) for every cut-off k, from monotonic gradient-boosted classifiers."""

    def __init__(self, levels, categorical=CATEGORICAL, numeric=NUMERIC):
        self.levels = sorted(levels)          # worst first
        self.categorical, self.numeric = categorical, numeric

    def _pipeline(self):
        columns = self.categorical + self.numeric
        encoder = ColumnTransformer(
            [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                                    encoded_missing_value=-1), self.categorical)],
            remainder="passthrough", verbose_feature_names_out=False)
        model = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.1, min_samples_leaf=200, random_state=SEED,
            categorical_features=[c in self.categorical for c in columns],
            monotonic_cst=[MONOTONIC.get(c, 0) for c in columns])
        return Pipeline([("encode", encoder), ("model", model)])

    def fit(self, X, y):
        X = X[self.categorical + self.numeric]
        self.models = {k: self._pipeline().fit(X, (y <= k).astype(int)) for k in self.levels[:-1]}
        return self

    def predict_proba(self, X):
        X = X[self.categorical + self.numeric]
        cum = np.column_stack([self.models[k].predict_proba(X)[:, 1] for k in self.levels[:-1]])
        cum = np.maximum.accumulate(cum, axis=1)                 # P(<=k) never falls as k grows
        cum = np.column_stack([cum, np.ones(len(X))])
        return np.diff(cum, axis=1, prepend=0)


class FrequencyBaseline:
    """Grade frequencies, overall or per group."""

    def __init__(self, levels, by=None):
        self.levels, self.by = sorted(levels), by

    def fit(self, X, y):
        y = pd.Series(np.asarray(y), index=X.index)
        self.overall = y.value_counts(normalize=True).reindex(self.levels, fill_value=1e-6).values
        self.groups = ({} if self.by is None else
                       {g: y[X[self.by] == g].value_counts(normalize=True).reindex(self.levels, fill_value=1e-6).values
                        for g in X[self.by].unique()})
        return self

    def predict_proba(self, X):
        if self.by is None:
            return np.tile(self.overall, (len(X), 1))
        return np.vstack([self.groups.get(g, self.overall) for g in X[self.by]])
