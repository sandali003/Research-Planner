# XAI user study: protocol and questionnaire

**Research question:** Does explainable, XAI-driven mitigation help used-car buyers understand a hidden
fault and choose the right action, compared with a scanner's trouble codes or a bare AI prediction?

**Proposal link:** Objective 4 (verification with certified mechanics) and the evaluation metric
*Mitigation Relevance (Domain Expert Score) ≥ 4 / 5*.

## 1. Design

- **Within-subject**, 6 scenarios (`scenarios.md`), each shown in one of three versions:
  - **A** Scanner: trouble codes only
  - **B** Prediction: fault name, confidence, severity
  - **C** Explainable system: B + likely cause (SHAP), repair target (counterfactual), reliability check, mitigation plan
- Every participant sees all six scenarios and every version twice. The version per scenario rotates
  between three groups so each scenario is seen in every version equally often:

| Group | S1 | S2 | S3 | S4 | S5 | S6 |
|---|---|---|---|---|---|---|
| 1 | A | B | C | A | B | C |
| 2 | B | C | A | B | C | A |
| 3 | C | A | B | C | A | B |

- Scenario order is shuffled per participant. Use a multiple of 3 participants.

## 2. Participants

| Group | Number | Who |
|---|---|---|
| Buyers | 12–15 (multiple of 3) | Adults who have bought or plan to buy a used car; no mechanical training |
| Experts | 2–3 | Certified mechanics (the two interviewed for the proposal, if possible) |

Session length: about 20 minutes (buyers), 30 minutes (mechanics).

## 3. Procedure

1. Consent (section 6) and two background questions (age group; has bought a used car: yes / no).
2. One practice scenario (not scored).
3. Six scenarios in the participant's group order. For each, show the readings table and the
   assigned version only, then ask Q1–Q5.
4. End questions (E1–E2).

Mechanics see every scenario in **version C** with the readings and answer M1–M5.

## 4. Buyer questionnaire (per scenario)

**Q1. Which part of the car most likely has a problem?**
☐ Battery / charging system ☐ Cooling system ☐ Engine mounts / ignition (vibration)
☐ No problem ☐ I don't know
*(scored against the answer key in `scenarios.md`)*

**Q2. What would you do?**
☐ Buy ☐ Negotiate the price and repair the named part ☐ Get a full inspection before buying
☐ Take another reading before deciding ☐ Walk away
*(scored against the recommended decision, confirmed with the mechanics before the study)*

**Q3. I understand what the result means.** 1 Strongly disagree – 5 Strongly agree

**Q4. I trust this result.** 1–5

**Q5. I know what to do next.** 1–5

**End questions**
- E1. Which kind of result would you want when buying a car? (show one example of A, B and C)
- E2. Anything that was confusing? (free text)

## 5. Mechanic form (version C, per scenario)

- **M1.** Is the *likely cause* correct for these readings? Yes / Partly / No
- **M2.** Is the *repair target* (counterfactual) realistic? 1–5
- **M3.** How useful is the mitigation plan (immediate actions + longevity tips)? 1–5 *(proposal target ≥ 4)*
- **M4.** Is any advice unsafe or wrong? Yes (which) / No
- **M5.** For S6: is the *low reliability* warning appropriate? Yes / No / Not sure

## 6. Consent text

> This study is part of an undergraduate research project at SLIIT (project J26-IT-386). You will look
> at six example vehicle check results and answer short questions. There are no right or wrong answers
> about you; we are testing the system. No personal data except your age group is recorded, answers are
> anonymous, and you can stop at any time. Do you agree to take part? ☐ Yes ☐ No

Check with the supervisor whether faculty ethics approval is needed before running the study.

## 7. Analysis

| Measure | Data | Test |
|---|---|---|
| Correct problem (Q1) | correct / wrong per version | Cochran's Q, then pairwise McNemar (A vs C, B vs C) |
| Correct decision (Q2) | correct / wrong per version | Cochran's Q, pairwise McNemar |
| Understanding, trust, actionability (Q3–Q5) | Likert 1–5 per version | Friedman, then Wilcoxon signed-rank (Holm correction) |
| Trust calibration | Q4 on S6 vs S1–S4, version C | Wilcoxon: trust should drop on the low-reliability case |
| Mitigation relevance (M3) | mean per scenario | Mean ≥ 4 / 5 (proposal target) |
| Cause correctness (M1) | Yes / Partly / No | Percentage |

Per participant, average each measure over the two scenarios seen in each version before testing.

**Expected result (hypotheses):**
- H1: Version C gives more correct problems (Q1) and decisions (Q2) than A and B.
- H2: Version C scores higher on understanding and actionability (Q3, Q5).
- H3: With version C, trust drops on S6 (low reliability), i.e. users trust the system appropriately.
- H4: Mechanics rate the mitigation plans ≥ 4 / 5.
