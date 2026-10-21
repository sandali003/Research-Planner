"""OBD-II trouble code knowledge (OBDex, CC0) for the expert system.

models/dtc_knowledge.json is built by build_dtc_knowledge.py: 7,200 powertrain
codes (P0xxx, P2xxx) with title, summary, likely causes ordered by likelihood,
symptoms, repair effort and flags, plus the AutoSense fault family of each code.
"""

from functools import lru_cache
from pathlib import Path
import json

KNOWLEDGE_FILE = Path(__file__).resolve().parent / "models" / "dtc_knowledge.json"

# Faults found by the AI models or the rules that a code of this family confirms
CONFIRMS = {
    "misfire": {"Abnormal_Vibration", "Engine_Abnormality_Suspected", "Hidden_Anomaly", "Rough_Idle"},
    "cooling": {"Cooling_System_Warning", "Running_Hot"},
    "charging": {"Charging_System_Warning"},
}
MAX_CAUSES = 3


@lru_cache(maxsize=1)
def _codes():
    if not KNOWLEDGE_FILE.exists():
        return {}
    return json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))["codes"]


def lookup(code):
    return _codes().get(str(code).strip().upper())


def severity(entry):
    """Limp mode possible -> High; check engine light -> Medium; otherwise Low."""
    if entry["flags"].get("limp_mode_possible"):
        return "High"
    if entry["flags"].get("mil"):
        return "Medium"
    return "Low"


def fault_name(code):
    return f"DTC_{code}"


def code_of(fault):
    return fault[4:] if fault.startswith("DTC_") else None
