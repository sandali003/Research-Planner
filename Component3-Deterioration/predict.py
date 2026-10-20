
import joblib
import pandas as pd

from data_prep import PROBLEM_SYNONYMS

model = joblib.load("models/solution_prediction_model.joblib")

service_history = input("Enter service history: ").strip().replace(",", ";")
common_problem = input("Enter common problem: ").strip()

if not common_problem:
    raise SystemExit("Common problem is required.")

# Clean the input the same way the training data was cleaned
common_problem = PROBLEM_SYNONYMS.get(common_problem, common_problem)
record = pd.DataFrame([{
    "SERVICE HISTORY": service_history,
    "COMMON PROBLEM": common_problem,
}])

probabilities = model.predict_proba(record)[0]
top = probabilities.argsort()[::-1][:3]

print("\nPredicted solution:", model.classes_[top[0]],
      f"({probabilities[top[0]] * 100:.1f}% confidence)")
print("Other possible solutions:")
for i in top[1:]:
    print(f"  {model.classes_[i]} ({probabilities[i] * 100:.1f}%)")
