"""
conflict_resolution.py

Score-based medication conflict resolution.

Scoring formula per (medication_name, dosage, frequency) candidate:
    score = source_priority + appearance_count + recency_bonus

Where:
    source_priority  — hospital_discharge=3, clinic_emr=2, patient_reported=1
    appearance_count — number of distinct sources reporting this exact
                       (dosage, frequency) combination
    recency_bonus    — +1 if any supporting record is within the last 7 days,
                       0 otherwise

The candidate with the highest score is chosen as the resolved version.
Ties are broken by source_priority of the highest-priority source
supporting that candidate.
"""

from datetime import datetime, timedelta, timezone

SOURCE_PRIORITY = {
    "hospital_discharge": 3,
    "clinic_emr": 2,
    "patient_reported": 1
}

RECENCY_DAYS = 7


def _to_aware(dt):
    """Ensure datetime is timezone-aware for safe comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def score_candidates(med_name: str, records: list) :
    """
    Given all medication records for a patient, find every reported
    (dosage, frequency) pair for med_name and compute a score for each.

    Returns a dict with:
        winner       — { dosage, frequency, score, supporting_sources }
        all_scores   — list of all candidates with their scores
        scoring_breakdown — human-readable explanation
    """
    now = datetime.now(timezone.utc)
    recency_cutoff = now - timedelta(days=RECENCY_DAYS)

    # Build candidates: { (dosage, frequency) -> { sources, timestamps } }
    candidates = {}

    for record in records:
        source = record.get("source", "")
        timestamp = _to_aware(record.get("timestamp"))

        for med in record.get("medications", []):
            if med.get("name", "").lower().strip() != med_name.lower().strip():
                continue

            dosage = (med.get("dosage") or "").lower().strip()
            frequency = (med.get("frequency") or "").lower().strip()
            key = (dosage, frequency)

            if key not in candidates:
                candidates[key] = {
                    "dosage": dosage,
                    "frequency": frequency,
                    "sources": [],
                    "timestamps": []
                }

            candidates[key]["sources"].append(source)
            if timestamp:
                candidates[key]["timestamps"].append(timestamp)

    if not candidates:
        return None

    # Score each candidate
    scored = []
    for (dosage, frequency), data in candidates.items():
        sources = data["sources"]
        timestamps = data["timestamps"]

        appearance_count = len(set(sources))  # distinct sources

        max_priority = max(
            SOURCE_PRIORITY.get(s, 0) for s in sources
        )

        recency_bonus = 1 if any(
            t >= recency_cutoff for t in timestamps
        ) else 0

        total_score = max_priority + appearance_count + recency_bonus

        scored.append({
            "dosage": dosage,
            "frequency": frequency,
            "score": total_score,
            "breakdown": {
                "source_priority": max_priority,
                "appearance_count": appearance_count,
                "recency_bonus": recency_bonus
            },
            "supporting_sources": list(set(sources))
        })

    # Sort: highest score first, tie-break by source_priority
    scored.sort(
        key=lambda x: (x["score"], x["breakdown"]["source_priority"]),
        reverse=True
    )

    winner = scored[0]

    return {
        "medication_name": med_name,
        "winner": winner,
        "all_scores": scored,
        "scoring_breakdown": (
            f"'{winner['dosage']} {winner['frequency']}' chosen — "
            f"score {winner['score']} "
            f"(priority={winner['breakdown']['source_priority']}, "
            f"appearances={winner['breakdown']['appearance_count']}, "
            f"recency={winner['breakdown']['recency_bonus']}), "
            f"supported by: {', '.join(winner['supporting_sources'])}"
        )
    }
