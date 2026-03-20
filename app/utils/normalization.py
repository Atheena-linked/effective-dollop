def normalize_dosage(dosage: str):
    """Lowercase and remove spaces from a dosage string. e.g. '100 MG' -> '100mg'."""

    if not dosage:
        return ""
    return dosage.lower().replace(" ","")


def normalize_frequency(freq: str):
    """Lowercase and strip whitespace from a frequency string. e.g. ' Once Daily ' -> 'once daily'."""
    if not freq:
        return ""
    return freq.lower().strip()