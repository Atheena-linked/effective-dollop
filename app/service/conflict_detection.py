from collections import defaultdict
from app.utils.normalization import normalize_dosage,normalize_frequency

SOURCE_PRIORITY = {
    "hospital": 3,
    "clinic": 2,
    "patient": 1
}

def detect_conflicts(records):

    med_map = defaultdict(list)

    for record in records:
        source = record["source"]

        for med in record["medications"]:
            name = med["name"].lower()
            med_map[name].append({
                "source": source,
                "dosage": normalize_dosage(med.get("dosage")),
                "frequency": normalize_frequency(med.get("frequency")),
                "priority": SOURCE_PRIORITY.get(source, 0)
            })

    conflicts = []

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
    