from collections import defaultdict
from app.utils.normalization import normalize_dosage,normalize_frequency
from datetime import datetime
from app.service.load_rules import load_conflict_rules


SOURCE_PRIORITY = {
    "hospital": 3,
    "clinic": 2,
    "patient": 1
}

#helper function for scalable and consistent format of conflicts
def build_conflict(medication_name, conflict_type, entries, severity="medium", description=None):
    return {
        "medication_name": medication_name,
        "conflict_type": conflict_type,
        "entries": entries,
        "severity": severity,
        "description": description,
        "created_at": datetime.utcnow(),
        "status": "active"
    }



def build_conflict(medication_name, conflict_type, entries, severity="medium", description=None):
    return {
        "medication_name": medication_name,
        "conflict_type": conflict_type,
        "entries": entries,
        "severity": severity,
        "description": description,
        "created_at": datetime.utcnow(),
        "status": "active"
    }


def build_med_index(records):
    """
    Returns:
        meds_by_source: { source -> set of med names }
        med_map:        { med_name -> list of { source, dosage, frequency, priority } }
    """

    meds_by_source = defaultdict(set)
    med_map = defaultdict(list)

    for record in records:
        source = record["source"]
        for med in record["medications"]:
            name = med["name"].lower().strip()
            meds_by_source[source].add(name)
            med_map[name].append({
                "source": source,
                "dosage": normalize_dosage(med.get("dosage")),
                "frequency": normalize_frequency(med.get("frequency")),
                "priority": SOURCE_PRIORITY.get(source, 0)
            })

    return meds_by_source, med_map


def detect_missing_medication_conflicts(meds_by_source, med_map):
    """
    A drug appears in source A but is absent from source B entirely.
    We only report each (drug, missing_source) pair once.
    """
    conflicts = []
    all_sources = list(meds_by_source.keys())
    seen = set()  # avoid duplicate (drug, source_b) pairs

    for source_a in all_sources:
        for source_b in all_sources:
            if source_a == source_b:
                continue

            meds_a = meds_by_source[source_a]
            meds_b = meds_by_source[source_b]

            missing_meds = meds_a - meds_b
            for med in missing_meds:
                key = (med, source_b)
                if key in seen:
                    continue
                seen.add(key)

                entry_list = []
                for entry in med_map[med]:
                    if entry["source"] == source_a:
                        entry_list.append({
                            "source": source_a,
                            "dosage": entry["dosage"],
                            "frequency": entry["frequency"],
                            "timestamp": datetime.utcnow()
                        })
                        break

                entry_list.append({
                    "source": source_b,
                    "dosage": None,
                    "frequency": None,
                    "timestamp": datetime.utcnow()
                })

                conflicts.append(build_conflict(med, "missing_medication", entry_list))

    return conflicts




def detect_dosage_and_freq_conflicts(med_map):
    """
    Same drug reported by multiple sources with different dosage or frequency.
    """
    conflicts = []
    dosages = set()
    frequencies = set()
    for med_name, entries in med_map.items():
        if len(entries) < 2:
            continue  # only one source so there is nothing to compare with

        

        for entry in entries:
            dosage_value = entry["dosage"]
            frequency_value = entry["frequency"]

            dosages.add(dosage_value)
            frequencies.add(frequency_value)

        if len(dosages) > 1:
            entry_list = []

            for entry in entries:
                entry_list.append({
                    "source": entry["source"],
                    "dosage": entry["dosage"],
                    "frequency": entry["frequency"],
                    "timestamp": datetime.utcnow()
                })

            conflict = build_conflict(
                med_name,
                "dosage_conflict",
                entry_list
            )

    

        if len(frequencies) > 1:
            
            entry_list = []

            for entry in entries:
                entry_list.append({
                    "source": entry["source"],
                    "dosage": entry["dosage"],
                    "frequency": entry["frequency"],
                    "timestamp": datetime.utcnow()
                })

            conflict = build_conflict(
                med_name,
                "frequency_conflict",
                entry_list
            )

            conflicts.append(conflict)
    
    return conflicts



def detect_drug_interactions(med_map):
    """
    Checks every pair of drugs the patient is on against conflict_rules.json.
    Flags combinations listed as dangerous (e.g. Aspirin + Ibuprofen).
    """
    rules = load_conflict_rules()          # list of rule dicts from JSON
    patient_meds = set(med_map.keys())     # already lowercased by build_med_index
    conflicts = []

    for rule in rules:
        drug_1 = rule["drug_1"].lower().strip()
        drug_2 = rule["drug_2"].lower().strip()

        if drug_1 in patient_meds and drug_2 in patient_meds:
            # Build combined entry list from both drugs' sources
            entry_list = []
            for med_name in [drug_1, drug_2]:
                for e in med_map[med_name]:
                    entry_list.append({
                        "source": e["source"],
                        "medication": med_name,
                        "dosage": e["dosage"],
                        "frequency": e["frequency"],
                        "timestamp": datetime.utcnow()
                    })

            conflicts.append(
                build_conflict(
                    medication_name=f"{drug_1} + {drug_2}",
                    conflict_type="drug_interaction",
                    entries=entry_list,
                    severity=rule.get("severity", "medium"),
                    description=rule.get("description")
                )
            )

    return conflicts

def detect_conflicts(records):
    meds_by_source, med_map = build_med_index(records)

    conflicts = (
        detect_missing_medication_conflicts(meds_by_source, med_map)
        + detect_dosage_and_freq_conflicts(med_map)
        + detect_drug_interactions(med_map)
    )

    return conflicts