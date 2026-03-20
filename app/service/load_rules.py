import json
from pathlib import Path

_RULES_PATH = Path(__file__).parent.parent / "data" / "conflict_rules.json"

def load_conflict_rules():
    with open("app/data/conflict_rules.json", "r") as file:
        data = json.load(file)
    return data["conflicts"]