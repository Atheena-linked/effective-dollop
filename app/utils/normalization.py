def normalize_dosage(dosage: str):
    if not dosage:
        return ""
    return dosage.lower().replace(" ","")


def normalize_frequency(freq: str):
    if not freq:
        return ""
    return freq.lower().strip()