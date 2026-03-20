import json
from pathlib import Path

_RULES_PATH = Path(__file__).parent.parent / "data" / "conflict_rules.json"

with open(_RULES_PATH, "r") as f:
    _CONFLICT_RULES = json.load(f)["conflicts"]

def load_conflict_rules():
    return _CONFLICT_RULES