from collections import defaultdict
from app.utils.normalization import normalize_dosage,normalize_frequency
from datetime import datetime

SOURCE_PRIORITY = {
    "hospital": 3,
    "clinic": 2,
    "patient": 1
}

#helper function for scalable and consistent format of conflicts
def build_conflict(medication_name, conflict_type, entries):
    return {
        "medication_name": medication_name,
        "conflict_type": conflict_type,
        "entries": entries,
        "created_at": datetime.utcnow(),
        "status": "active"
    }

def detect_conflicts(records):

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

    conflicts = []

    all_sources = list(meds_by_source.keys())

    for source_a in all_sources:
        for source_b in all_sources:

            if source_a == source_b:
                continue

            meds_a = meds_by_source[source_a]
            meds_b = meds_by_source[source_b]

            missing_meds = meds_a - meds_b
            for med in missing_meds:
                entry_list = []

                # Getting data such as freq and dosage from source a where med exist
                for entry in med_map[med]:
                    if entry["source"] == source_a:
                        entry_list.append({
                            "source": source_a,
                            "dosage": entry["dosage"],
                            "frequency": entry["frequency"],
                            "timestamp": datetime.utcnow()
                        })
                        break

                # adding missing source and data
                entry_list.append({
                    "source": source_b,
                    "dosage": None,
                    "frequency": None,
                    "timestamp": datetime.utcnow()
                })

                conflicts.append(
                    build_conflict(
                        med,
                        "missing_medication",
                        entry_list
                    )
                )
    for med_name, entries in med_map.items():

        dosages = set()
        frequencies = set()

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

            conflicts.append(conflict)

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
