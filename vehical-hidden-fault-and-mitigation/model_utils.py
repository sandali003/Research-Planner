
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight


class LabelEncodedClassifier(ClassifierMixin, BaseEstimator):
    """Wraps a classifier that needs integer labels (e.g. XGBoost).

    Text labels are encoded for training and decoded on prediction,
    so the saved model still returns labels such as "Normal".
    """

    def __init__(self, estimator, balance_classes=True):
        self.estimator = estimator
        self.balance_classes = balance_classes

    def fit(self, X, y):
        self.label_encoder_ = LabelEncoder()
        y_encoded = self.label_encoder_.fit_transform(y)
        self.classes_ = self.label_encoder_.classes_

        # Same idea as class_weight="balanced" in Random Forest
        sample_weight = None
        if self.balance_classes:
            sample_weight = compute_sample_weight("balanced", y_encoded)

        self.estimator_ = clone(self.estimator)
        self.estimator_.fit(X, y_encoded, sample_weight=sample_weight)
        return self

    def predict(self, X):
        encoded = np.asarray(self.estimator_.predict(X)).astype(int)
        return self.label_encoder_.inverse_transform(encoded)

    def predict_proba(self, X):
        return self.estimator_.predict_proba(X)
