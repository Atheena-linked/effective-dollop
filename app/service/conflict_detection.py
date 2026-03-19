from collections import defaultdict

def detect_conflicts(records):

    med_map = defaultdict(list)

    for record in records:
        source = record["source"]

        for med in record["medications"]:
            name = med["name"].lower()
            med_map[name].append({
                "source": source,
                "dosage": med["dosage"],
                "frequency": med["frequency"]
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
                "type" : "dosage_conflict",
                "values" : list(dosages)})

        if len(frequencies) > 1:
            conflicts.append({
                "medication": med_name,
                "type": "frequency_conflict",
                "values": list(frequencies)
            })

    return conflicts

    