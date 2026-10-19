
import pandas as pd
import joblib

from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score

from data_prep import load_service_data

print("Loading service datasets...")

# 1. Load and clean both service datasets (Kaggle 3000 + synthetic 6000)
df = load_service_data()

print("All records:", len(df))
print("Different solutions:", df["SOLUTION USED"].nunique())

# 2. Remove repeated records for evaluation
# Most rows are copies of each other. If copies land in both train and test,
# the model is tested on records it has already seen and accuracy looks too high.
unique_df = df.drop_duplicates(["input_text", "SOLUTION USED"]).reset_index(drop=True)
print("Unique records used for evaluation:", len(unique_df))


INPUTS = ["SERVICE HISTORY", "COMMON PROBLEM"]


def make_model():
    # Problem and history get separate text features. History gets a lower
    # weight so the problem decides the solution (with one shared text field,
    # history words like "Oil Change" could override the actual problem).
    text = ColumnTransformer(
        [
            ("problem", TfidfVectorizer(ngram_range=(1, 2)), "COMMON PROBLEM"),
            ("history", TfidfVectorizer(ngram_range=(1, 2)), "SERVICE HISTORY"),
        ],
        transformer_weights={"problem": 1.0, "history": 0.3},
    )
    return Pipeline([
        ("text", text),
        ("classifier", LogisticRegression(max_iter=2000, C=10)),
    ])


# 3. Cross-validate so the same input text never appears in train and test
cv = GroupKFold(n_splits=5)
model_pred = pd.Series("", index=unique_df.index)
lookup_pred = pd.Series("", index=unique_df.index)

for train_idx, test_idx in cv.split(unique_df, groups=unique_df["input_text"]):
    train = unique_df.iloc[train_idx]
    test = unique_df.iloc[test_idx]

    model = make_model()
    model.fit(train[INPUTS], train["SOLUTION USED"])
    model_pred.iloc[test_idx] = model.predict(test[INPUTS])

    # Baseline: most common solution for the same problem in the training fold
    lookup = train.groupby("COMMON PROBLEM")["SOLUTION USED"].agg(lambda s: s.mode()[0])
    lookup_pred.iloc[test_idx] = test["COMMON PROBLEM"].map(lookup).fillna("").values

y = unique_df["SOLUTION USED"]
print("\nEvaluation on unseen service records (5-fold):")
print("  Model         accuracy:", round(accuracy_score(y, model_pred) * 100, 2), "%",
      " macro F1:", round(f1_score(y, model_pred, average="macro", zero_division=0), 3))
print("  Lookup table  accuracy:", round(accuracy_score(y, lookup_pred) * 100, 2), "%",
      " macro F1:", round(f1_score(y, lookup_pred, average="macro", zero_division=0), 3))

# 4. Train the final model on all records (repeats keep the real frequencies)
model = make_model()
model.fit(df[INPUTS], df["SOLUTION USED"])

# 5. Save model
joblib.dump(model, "solution_prediction_model.joblib")

print("\nModel saved successfully!")
print("File: solution_prediction_model.joblib")
