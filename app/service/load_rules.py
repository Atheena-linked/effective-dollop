import json

def load_conflict_rules():
    with open("app/data/conflict_rules.json", "r") as file:
        data = json.load(file)
    return data["conflicts"]