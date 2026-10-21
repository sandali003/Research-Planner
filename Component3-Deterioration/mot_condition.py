"""Condition grades from MOT test outcomes (Component 3, step 1).

The MOT gives no condition score, only the defects found. Instead of
inventing weights, the grade follows the official DVSA defect categories
(MOT inspection manual, since May 2018), worst category found wins:

  Overall grade (whole vehicle)          Component grade (one component group)
    5 Good       no defect or advisory     4 Good       nothing recorded
    4 Wear       advisories only           3 Wear       advisory
    3 Minor      minor defect (passes)     2 Minor      minor defect
    2 Major      failure                   1 Major      failure or dangerous
    1 Dangerous  dangerous failure                      (dangerous is rare per component)

Higher is better. Model names are mapped to a platform so the Japan-only
models sold in Sri Lanka share the baseline of their UK equivalents:
Vitz is the Yaris; Axio, Allion and Premio are Corolla-family cars.
"""

import numpy as np
import pandas as pd

OVERALL_GRADES = {5: "Good", 4: "Wear", 3: "Minor", 2: "Major", 1: "Dangerous"}
COMPONENT_GRADES = {4: "Good", 3: "Wear", 2: "Minor", 1: "Major"}

# Component groups used by Component 3 (MOT checks these; engine, battery,
# cooling and transmission are not part of the MOT)
COMPONENTS = ["brakes", "suspension", "steering", "tyres", "emissions_leaks"]

PLATFORM = {
    "Yaris": "Yaris", "Vitz": "Yaris",
    "Corolla": "Corolla", "Axio": "Corolla", "Allion": "Corolla", "Premio": "Corolla",
}


def overall_grade(df):
    return pd.Series(np.select(
        [df["n_dangerous"] > 0, df["n_failures"] > 0, df["n_minor"] > 0, df["n_advisories"] > 0],
        [1, 2, 3, 4], default=5), index=df.index, name="grade")


def component_grade(df, component):
    return pd.Series(np.select(
        [df[f"fail_{component}"] > 0, df[f"minor_{component}"] > 0, df[f"adv_{component}"] > 0],
        [1, 2, 3], default=4), index=df.index, name=f"grade_{component}")


def add_grades(df):
    """Platform, overall grade and one grade per component."""
    df = df.copy()
    df["platform"] = df["model"].map(PLATFORM)
    df["grade"] = overall_grade(df)
    for c in COMPONENTS:
        df[f"grade_{c}"] = component_grade(df, c)
    return df
