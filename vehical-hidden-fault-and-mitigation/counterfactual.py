"""Counterfactual explanations: what has to change for the model to call a reading normal.

SHAP says which sensor drives a fault; the counterfactual says how far it
has to come back. That gives the mitigation a measurable repair target
("battery voltage has to come down to about 14.6 V") that can be checked
with a new reading after the repair.

Only sensors a repair can bring back are changed (voltage, temperature,
vibration); engine speed and load describe how the car is driven. Each
sensor group is moved step by step towards its normal (median) value and
the smallest move that makes the model say "normal" is kept.
"""

import numpy as np
import pandas as pd

from expert_system import FEATURE_GROUP, GROUP_LABELS

ACTIONABLE_GROUPS = ("voltage", "temperature", "vibration")
STEPS = np.linspace(0, 1, 41)[1:]  # fraction of the way back to normal
UNITS = {"voltage": "V", "temperature": "°C", "vibration": "g"}
DECIMALS = {"voltage": 1, "temperature": 0, "vibration": 2}
VIBRATION_AXES = ("x", "y", "z")


def _is_magnitude(feature):
    return "magnitude" in feature


def _with_magnitude(df, features):
    """Recompute the vibration magnitude feature from its axes, if the model uses one."""
    for magnitude in (f for f in features if _is_magnitude(f)):
        axes = [magnitude.replace("magnitude", a) for a in VIBRATION_AXES]
        df[magnitude] = np.sqrt(sum(df[a] ** 2 for a in axes))
    return df


def _path(row, moved, normal, features):
    """One row per step, with the moved features part of the way to normal."""
    rows = pd.concat([row] * len(STEPS), ignore_index=True)
    for f in moved:
        rows[f] = row[f].iloc[0] + STEPS * (normal[f] - row[f].iloc[0])
    return _with_magnitude(rows, features)


def _describe(group, row, target, features, group_of, healthy):
    """Readable change for one sensor group (vibration is reported as its overall level)."""
    feats = [f for f in features if group_of(f) == group]
    shown = [f for f in feats if _is_magnitude(f)] or feats
    changes = []
    for f in shown:
        before, after = float(row[f].iloc[0]), float(target[f])
        change = {
            "feature": f, "group": group, "label": GROUP_LABELS[group],
            "from": round(before, 3), "to": round(after, 3),
            "direction": "down" if after < before else "up",
        }
        if healthy and f in healthy:
            change["healthy_range"] = [round(float(v), 3) for v in healthy[f]]
        changes.append(change)
    return changes


def _text(changes):
    parts = []
    for c in changes:
        unit, dp = UNITS[c["group"]], DECIMALS[c["group"]]
        verb = "come down" if c["direction"] == "down" else "come up"
        text = f"{c['label']} has to {verb} from {c['from']:.{dp}f} {unit} to about {c['to']:.{dp}f} {unit}"
        if "healthy_range" in c:
            lo, hi = c["healthy_range"]
            text += f" (healthy range {lo:.{dp}f}-{hi:.{dp}f} {unit})"
        parts.append(text)
    return " and ".join(parts)


def find_counterfactual(row, features, is_normal, normal, group_of=None, healthy=None):
    """Smallest move of one sensor group back towards normal that makes the model say normal.

    row:       one-row DataFrame with the model's features
    is_normal: function(DataFrame) -> boolean array, True where the model says normal
    normal:    normal (median) value per feature
    group_of:  feature -> sensor group (default: expert_system.FEATURE_GROUP)
    healthy:   optional (low, high) healthy range per feature, shown with the target.
               The minimal change only reaches the model's boundary; the healthy
               range is where the repair should bring the sensor.
    Returns None when no move of the repairable sensors clears the fault.
    """
    group_of = group_of or FEATURE_GROUP.get
    groups = {}
    for f in features:
        g = group_of(f)
        if g in ACTIONABLE_GROUPS and not _is_magnitude(f):
            groups.setdefault(g, []).append(f)

    def first_normal(moved):
        path = _path(row, moved, normal, features)
        ok = np.asarray(is_normal(path))
        return (int(np.argmax(ok)), path) if ok.any() else (None, None)

    best = None
    for g, moved in groups.items():
        i, path = first_normal(moved)
        if i is not None and (best is None or STEPS[i] < best[0]):
            best = (STEPS[i], [g], path.iloc[i])
    if best is None and len(groups) > 1:  # no single sensor is enough: move all of them
        i, path = first_normal([f for fs in groups.values() for f in fs])
        if i is not None:
            best = (STEPS[i], list(groups), path.iloc[i])
    if best is None:
        return None

    step, changed, target = best
    changes = [c for g in changed for c in _describe(g, row, target, features, group_of, healthy)]
    return {
        "sensor_groups": changed,
        "changes": changes,
        "fraction_back_to_normal": round(float(step), 3),
        "text": _text(changes),
    }
