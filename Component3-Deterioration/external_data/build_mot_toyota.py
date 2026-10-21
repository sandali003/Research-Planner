"""Build a Toyota dataset for Component 3 from the UK MOT anonymised test data (DVSA).

Source (Open Government Licence v3): https://open.data.dvsa.gov.uk/mot-anonymised/index.html
  dft_test_result_<year>.zip   one row per MOT test (vehicle, mileage, first use date, result)
  dft_test_item_<year>.zip     failure / advisory items of each test
  dft_item_detail_extract.csv, dft_item_group_extract.csv   item -> component section lookups

Output (one row per normal MOT test of a target Toyota model, cars only):
  mot_toyota_<year>.csv    every row
  mot_toyota_<year>.xlsx   README, Summary and one sheet per model (Excel limit: 1,048,575 rows)

Columns: vehicle_id (same car across years), model, test_date, first_use_date, age_years,
odometer_km, km_per_year, fuel_type, engine_cc, test_result, failures / advisories /
dangerous counts, and fail_<component> / adv_<component> counts per component group.

Run:  python external_data/build_mot_toyota.py <folder with the downloaded files> [year] [--no-excel]
The folder needs test_result.csv (or the zip). Per-component counts also need test_item.csv
(or its zip) and a lookups/ folder with the two item lookup CSVs; without them the
output has pass/fail only.
"""

from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd

OUT_DIR = Path(__file__).resolve().parent

# Sri Lankan target models and their UK names (Vitz is sold as Yaris, Axio as Corolla)
TARGET_MODELS = {
    "COROLLA": "Corolla", "YARIS": "Yaris", "VITZ": "Vitz",
    "AXIO": "Axio", "COROLLA AXIO": "Axio", "ALLION": "Allion", "PREMIO": "Premio",
}
CAR_CLASS = 4
NORMAL_TEST = "NT"
MILES_TO_KM = 1.609344
CHUNK = 1_000_000
EXCEL_MAX_ROWS = 1_048_575

# MOT component sections (pre- and post-2018 manuals) -> one name per component group
SECTION_GROUP = {
    "brakes": "brakes", "steering": "steering", "suspension": "suspension",
    "tyres": "tyres", "road wheels": "wheels",
    "lamps, reflectors and electrical equipment": "lamps_electrical",
    "body, structure and general items": "body_structure", "body, chassis, structure": "body_structure",
    "exhaust, fuel and emissions": "emissions_leaks", "noise, emissions and leaks": "emissions_leaks",
    "driver's view of the road": "visibility", "visibility": "visibility",
    "seat belts and supplementary restraint systems": "seat_belts",
    "seat belt installation check": "seat_belts",
}
GROUPS = sorted(set(SECTION_GROUP.values()))
FAIL_CODES = {"F", "P"}   # failure, failure repaired at the test station (PRS)
ADVISORY_CODES = {"A"}
MINOR_CODES = {"M"}       # minor defect (passes, but recorded)
KINDS = {"fail": "n_failures", "minor": "n_minor", "adv": "n_advisories"}


def _sep(sample):
    """The MOT files are pipe-separated; older extracts use commas."""
    return "|" if sample.count("|") > sample.count(",") else ","


def read_csv_chunks(path, usecols=None, chunksize=CHUNK):
    """Yield chunks of a CSV, or of every CSV inside a zip (yearly zips may hold several)."""
    path = Path(path)
    if path.suffix.lower() != ".zip":
        with open(path, encoding="utf-8", errors="replace") as f:
            sep = _sep(f.readline())
        yield from pd.read_csv(path, sep=sep, usecols=usecols, chunksize=chunksize, low_memory=False,
                                  on_bad_lines="skip")  # a few rows have unquoted commas
        return
    with zipfile.ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if n.lower().endswith(".csv")):
            with z.open(name) as f:
                sep = _sep(f.readline().decode("utf-8", "replace"))
            with z.open(name) as f:
                yield from pd.read_csv(f, sep=sep, usecols=usecols, chunksize=chunksize, low_memory=False,
                                  on_bad_lines="skip")  # a few rows have unquoted commas


def find_file(folder, *names):
    """First existing file among the names (extracted CSV or downloaded zip)."""
    for name in names:
        if (folder / name).exists():
            return folder / name
    return None


def find_sources(folder, kind, year):
    """Data files of one kind ("result" or "item"): one extracted CSV, the yearly zip, or
    the monthly CSVs of the newer releases (test_result_202401.csv, ...) in any subfolder."""
    single = find_file(folder, f"test_{kind}.csv", f"dft_test_{kind}_{year}.zip")
    if single:
        return [single]
    return sorted(p for p in folder.rglob(f"test_{kind}_*.csv") if "__MACOSX" not in p.parts)


def item_groups(folder):
    """rfr_id -> component group for cars (class 4)."""
    detail = pd.read_csv(folder / "dft_item_detail_extract.csv")
    sections = pd.read_csv(folder / "dft_item_group_extract.csv")
    detail = detail[detail["test_class_id"] == CAR_CLASS]
    sections = sections[(sections["test_class_id"] == CAR_CLASS) & (sections["parent_id"] == 0)]
    names = dict(zip(sections["test_item_set_section_id"], sections["item_name"].str.lower().str.strip()))
    groups = detail["test_item_set_section_id"].map(names).map(SECTION_GROUP).fillna("other")
    return dict(zip(detail["rfr_id"], groups))


def chunks_of(paths):
    for path in paths:
        print(f"  reading {path.name}", flush=True)
        yield from read_csv_chunks(path)


def load_tests(paths):
    keep = []
    for chunk in chunks_of(paths):
        chunk.columns = chunk.columns.str.lower()
        # Newer files mix types in a column (e.g. test_class_id "4"), so compare as numbers
        for col in ("test_id", "vehicle_id", "test_class_id"):
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
        model = chunk["model"].astype(str).str.upper().str.strip()
        mask = ((chunk["make"].astype(str).str.upper().str.strip() == "TOYOTA")
                & model.isin(TARGET_MODELS)
                & (chunk["test_class_id"] == CAR_CLASS)
                & (chunk["test_type"] == NORMAL_TEST))
        part = chunk[mask].copy()
        part["model"] = model[mask].map(TARGET_MODELS)
        keep.append(part)
        print(f"  tests scanned: +{len(chunk):,}  kept so far: {sum(len(k) for k in keep):,}", flush=True)
    return pd.concat(keep, ignore_index=True)


def load_items(paths, test_ids, groups):
    counts = []
    for chunk in chunks_of(paths):
        chunk.columns = chunk.columns.str.lower()
        chunk["test_id"] = pd.to_numeric(chunk["test_id"], errors="coerce")
        chunk["rfr_id"] = pd.to_numeric(chunk["rfr_id"], errors="coerce")
        chunk = chunk[chunk["test_id"].isin(test_ids)]
        if chunk.empty:
            continue
        chunk["group"] = chunk["rfr_id"].map(groups).fillna("other")
        code = chunk["rfr_type_code"].astype(str).str.upper()
        chunk["kind"] = np.select([code.isin(FAIL_CODES), code.isin(MINOR_CODES), code.isin(ADVISORY_CODES)],
                                  ["fail", "minor", "adv"], default="other")
        # Dangerous is a mark on a failure item: it stays in fail_<group> and is also counted
        # in dangerous_<group>
        dangerous = chunk.get("dangerous_mark", pd.Series(index=chunk.index, dtype=object))
        marked = chunk[dangerous.astype(str).str.upper().eq("D")].assign(kind="dangerous")
        counts.append(pd.concat([chunk, marked]).groupby(["test_id", "kind", "group"]).size())
    if not counts:
        return pd.DataFrame(index=pd.Index([], name="test_id"))
    total = pd.concat(counts).groupby(level=[0, 1, 2]).sum()
    wide = total.unstack(["kind", "group"], fill_value=0)
    wide.columns = [f"{k}_{g}" for k, g in wide.columns]
    for kind, total_col in {**KINDS, "dangerous": "n_dangerous"}.items():
        cols = [c for c in wide.columns if c.startswith(kind + "_")]
        wide[total_col] = wide[cols].sum(axis=1) if cols else 0
    return wide


def build(folder, year):
    folder = Path(folder)
    results = find_sources(folder, "result", year)
    if not results:
        raise FileNotFoundError(f"No test_result.csv, dft_test_result_{year}.zip or test_result_*.csv in {folder}")
    print(f"Reading tests from {len(results)} file(s) ...")
    tests = load_tests(results)
    print(f"Target Toyota tests: {len(tests):,}")

    df = tests
    items_files = find_sources(folder, "item", year)
    lookups = find_file(folder, "lookups") or find_file(OUT_DIR.parent, "lookups")
    if items_files and lookups:
        print(f"Reading failure items from {len(items_files)} file(s) ...")
        items = load_items(items_files, set(tests["test_id"]), item_groups(lookups))
        df = tests.merge(items, left_on="test_id", right_index=True, how="left")
        count_cols = [c for c in df.columns if c.startswith(("fail_", "minor_", "adv_", "dangerous_", "n_"))]
        df[count_cols] = df[count_cols].fillna(0).astype(int)
        for total_col in [*KINDS.values(), "n_dangerous"]:
            if total_col not in df:
                df[total_col] = 0
        for kind in [*KINDS, "dangerous"]:
            for g in GROUPS + ["other"]:
                if f"{kind}_{g}" not in df:
                    df[f"{kind}_{g}"] = 0
    else:
        print("No failure item file (test_item.csv / dft_test_item_<year>.zip + lookups/): "
              "building pass/fail only, without per-component counts.")

    df["test_date"] = pd.to_datetime(df["test_date"], errors="coerce")
    df["first_use_date"] = pd.to_datetime(df["first_use_date"], errors="coerce")
    df["age_years"] = ((df["test_date"] - df["first_use_date"]).dt.days / 365.25).round(2)
    df["odometer_km"] = (pd.to_numeric(df["test_mileage"], errors="coerce") * MILES_TO_KM).round()
    df["km_per_year"] = (df["odometer_km"] / df["age_years"].clip(lower=0.5)).round()
    df = df[(df["age_years"] > 0) & (df["odometer_km"] > 0)]

    columns = (["vehicle_id", "test_id", "model", "test_date", "first_use_date", "age_years", "odometer_km",
                "km_per_year", "fuel_type", "cylinder_capacity", "test_result",
                "n_failures", "n_dangerous", "n_minor", "n_advisories"]
               + [f"{kind}_{g}" for kind in [*KINDS, "dangerous"] for g in GROUPS + ["other"]])
    df = df[[c for c in columns if c in df.columns]].rename(columns={"cylinder_capacity": "engine_cc"})
    df = df.sort_values(["model", "vehicle_id", "test_date"]).reset_index(drop=True)
    df["test_date"] = df["test_date"].dt.date
    df["first_use_date"] = df["first_use_date"].dt.date
    return df


def write_outputs(df, year, excel=True):
    csv_path = OUT_DIR / f"mot_toyota_{year}.csv"
    df.to_csv(csv_path, index=False)
    if not excel:
        print(f"Wrote {csv_path} ({len(df):,} rows)")
        return

    aggregations = dict(
        tests=("test_id", "size"), vehicles=("vehicle_id", "nunique"),
        median_age_years=("age_years", "median"), median_odometer_km=("odometer_km", "median"),
        fail_rate=("test_result", lambda r: round(float(r.isin(["F", "PRS"]).mean()), 3)),
    )
    if "n_failures" in df:
        aggregations.update(mean_failures=("n_failures", "mean"), mean_advisories=("n_advisories", "mean"))
    summary = df.groupby("model").agg(**aggregations).round(2).reset_index()
    readme = pd.DataFrame({"field": [
        "source", "licence", "rows", "vehicle_id", "age_years", "odometer_km", "km_per_year", "test_result",
        "n_failures / n_dangerous / n_minor / n_advisories", "fail_<group> / minor_<group> / adv_<group>",
        "model mapping", "note",
    ], "description": [
        f"UK MOT anonymised test data {year} (DVSA), https://open.data.dvsa.gov.uk/mot-anonymised/index.html",
        "Open Government Licence v3.0",
        "One normal MOT test (class 4 car) of a Toyota Corolla / Yaris / Vitz / Axio / Allion / Premio",
        "Anonymised vehicle ID, the same car keeps it across years (use it to follow deterioration)",
        "test date - first use date",
        "MOT odometer reading converted from miles to km",
        "odometer_km / age_years",
        "P passed, F failed, PRS pass after repair at the station (counts as a failure in fail_rate)",
        "Items found at the test: failures (F, or PRS = repaired at the station), dangerous failures, "
        "minor defects (pass, but recorded) and advisories (wear to watch)",
        "Failure / minor / advisory items per component group (brakes, steering, suspension, tyres, "
        "emissions_leaks, ...). Advisories show early wear before a failure",
        "UK sells Vitz as Yaris and Axio as Corolla; Allion/Premio are Japan-only and are rare in the UK",
        "UK roads and climate differ from Sri Lanka; use as a platform-equivalent reference",
    ]})

    xlsx_path = OUT_DIR / f"mot_toyota_{year}.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xl:
        readme.to_excel(xl, sheet_name="README", index=False)
        summary.to_excel(xl, sheet_name="Summary", index=False)
        for model, g in df.groupby("model"):
            if len(g) > EXCEL_MAX_ROWS:
                print(f"  {model}: {len(g):,} rows, Excel sheet keeps a random {EXCEL_MAX_ROWS:,} (full data in CSV)")
                g = g.sample(EXCEL_MAX_ROWS, random_state=0).sort_values(["vehicle_id", "test_date"])
            g.to_excel(xl, sheet_name=model[:31], index=False)
    print(summary.to_string(index=False))
    print(f"Wrote {csv_path} and {xlsx_path}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = args[0]
    year = args[1] if len(args) > 1 else "2023"
    write_outputs(build(folder, year), year, excel="--no-excel" not in sys.argv)
