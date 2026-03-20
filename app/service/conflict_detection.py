from collections import defaultdict
from app.utils.normalization import normalize_dosage,normalize_frequency

SOURCE_PRIORITY = {
    "hospital": 3,
    "clinic": 2,
    "patient": 1
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
                conflicts.append({
                    "medication": med,
                    "type": "missing_medication",
                    "present_in": source_a,
                    "missing_in": source_b,
                    "confidence": 1.0
                })

    for med_name, entries in med_map.items():

        dosages = set()
        frequencies = set()

        for entry in entries:
            dosage_value = entry["dosage"]
            frequency_value = entry["frequency"]

            dosages.add(dosage_value)
            frequencies.add(frequency_value)

        if len(dosages) > 1:
            conflicts.append({
                "medication": med_name,
                "type": "dosage_conflict",
                "values": list(dosages),
                "confidence": round(len(entries) / len(dosages), 2)
                })

        if len(frequencies) > 1:
            conflicts.append({
                "medication": med_name,
                "type": "frequency_conflict",
                "values": list(frequencies),
                "confidence": round(len(entries) / len(frequencies), 2)
                })

    return conflicts
    