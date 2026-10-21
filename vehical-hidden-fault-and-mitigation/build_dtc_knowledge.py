"""Builds the DTC knowledge base used by the expert system from OBDex.

Source: OBDex (https://github.com/foerbsnavi/obdex, data licence CC0):
raw_data/P0xxx_enriched.yaml and P2xxx_enriched.yaml (powertrain trouble codes).
Writes models/dtc_knowledge.json with the English fields only, plus the
AutoSense fault family each code belongs to, so the service loads a small JSON
file and needs no YAML library at run time.

Run once after updating the YAML files (needs PyYAML):
    python build_dtc_knowledge.py
"""

from pathlib import Path
import json
import re

import yaml

BASE_DIR = Path(__file__).resolve().parent
SOURCES = [BASE_DIR / "raw_data" / "P0xxx_enriched.yaml", BASE_DIR / "raw_data" / "P2xxx_enriched.yaml"]
OUT = BASE_DIR / "models" / "dtc_knowledge.json"

# AutoSense fault families: code ranges first, then title keywords
FAMILY_RANGES = {
    "misfire": [("P0300", "P0316"), ("P0350", "P0362")],
    "cooling": [("P0115", "P0119"), ("P0125", "P0128"), ("P0217", "P0217"), ("P0480", "P0485"),
                ("P2181", "P2185")],
    "charging": [("P0560", "P0563"), ("P0620", "P0628"), ("P2500", "P2505")],
}
FAMILY_KEYWORDS = {
    "misfire": r"misfire|ignition coil",
    "cooling": r"coolant|thermostat|cooling fan|engine over ?temperature",
    "charging": r"generator|alternator|system voltage|charging",
}
LIKELIHOOD_ORDER = {"high": 0, "medium": 1, "low": 2}


def family(code, title):
    for fam, ranges in FAMILY_RANGES.items():
        if any(lo <= code <= hi for lo, hi in ranges):
            return fam
    for fam, pattern in FAMILY_KEYWORDS.items():
        if re.search(pattern, title, re.IGNORECASE):
            return fam
    return "engine"


def en(value):
    return value.get("en") if isinstance(value, dict) else value


def first_sentences(text, n=2):
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return " ".join(parts[:n])


def main():
    knowledge = {}
    for path in SOURCES:
        for e in yaml.safe_load(path.read_text(encoding="utf-8")):
            code, title = e["code"], en(e.get("title")) or ""
            causes = sorted(e.get("common_causes") or [], key=lambda c: LIKELIHOOD_ORDER.get(c.get("likelihood"), 3))
            repair = e.get("repair") or {}
            flags = e.get("flags") or {}
            knowledge[code] = {
                "title": title,
                "summary": first_sentences(en(e.get("description"))),
                "family": family(code, title),
                "components": e.get("affected_components") or [],
                "causes": [{"text": en(c.get("label")), "likelihood": c.get("likelihood")} for c in causes],
                "symptoms": [en(s) for s in e.get("symptoms") or []],
                "repair": {"difficulty": repair.get("difficulty"), "diy_possible": repair.get("diy_possible"),
                           "cost_eur": repair.get("estimated_cost_eur"), "hours": repair.get("estimated_hours")},
                "flags": {k: bool(flags.get(k)) for k in ("mil", "emissions_relevant", "limp_mode_possible")},
                "related": e.get("related_codes") or [],
            }
    OUT.write_text(json.dumps({"source": "OBDex (CC0), https://github.com/foerbsnavi/obdex",
                               "codes": knowledge}, ensure_ascii=False), encoding="utf-8")
    fams = {}
    for v in knowledge.values():
        fams[v["family"]] = fams.get(v["family"], 0) + 1
    print(f"Wrote {len(knowledge)} codes to {OUT} ({OUT.stat().st_size / 1e6:.1f} MB); families {fams}")


if __name__ == "__main__":
    main()
