"""
Seed script — 20 patients covering all base cases and edge cases.
Run from the project root:
    python seed.py

Coverage map:
    Base cases:
        - Clean patient, single source
        - Clean patient, all sources agree
        - Dosage conflict across 2 sources
        - Frequency conflict across 2 sources
        - Missing medication conflict
        - Drug interaction (aspirin + ibuprofen)
        - Drug interaction (paracetamol + alcohol)
        - Drug interaction (metformin + alcohol)

    Edge cases:
        - Three-way dosage conflict (all 3 sources disagree)
        - Dosage AND frequency conflict on same drug
        - Multiple conflict types on same patient simultaneously
        - Missing med AND drug interaction on same patient
        - Drug present in only one source (single-source patient)
        - Medication with missing dosage field (None/empty)
        - Medication with missing frequency field (None/empty)
        - Duplicate medication name across sources (same name, same dose — no conflict)
        - Case sensitivity edge case (MeTfOrMiN vs metformin — should normalize)
        - Whitespace edge case in drug name ("  aspirin  ")
        - Dosage with different units same value (500mg vs 0.5g — currently not normalized)
        - Patient with resolved conflict (seeded directly as resolved)
"""

import asyncio
from datetime import datetime, timedelta
import random
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "medication_db")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
medication_collection = db["medications"]
conflict_collection = db["conflicts"]

SOURCES = ["clinic_emr", "hospital_discharge", "patient_reported"]

SOURCE_PRIORITY = {
    "hospital_discharge": 3,
    "clinic_emr": 2,
    "patient_reported": 1
}

# ─────────────────────────────────────────────
# PATIENTS
# Each entry: (patient_id, [(source, [medications])])
# ─────────────────────────────────────────────

PATIENTS = [

    # ── BASE CASES ──────────────────────────────────────────────────────────

    # P001 — clean patient, single source, no conflicts possible
    ("P001", [
        ("clinic_emr", [
            {"name": "levothyroxine", "dosage": "50mcg", "frequency": "once daily"},
        ]),
    ]),

    # P002 — clean patient, all three sources agree exactly, no conflicts
    ("P002", [
        ("clinic_emr", [
            {"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"},
            {"name": "omeprazole", "dosage": "20mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"},
            {"name": "omeprazole", "dosage": "20mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"},
            {"name": "omeprazole", "dosage": "20mg", "frequency": "once daily"},
        ]),
    ]),

    # P003 — simple dosage conflict on one drug across 2 sources
    ("P003", [
        ("clinic_emr", [
            {"name": "metformin", "dosage": "500mg", "frequency": "twice daily"},
        ]),
        ("hospital_discharge", [
            {"name": "metformin", "dosage": "1000mg", "frequency": "twice daily"},
        ]),
    ]),

    # P004 — simple frequency conflict on one drug across 2 sources
    ("P004", [
        ("clinic_emr", [
            {"name": "amlodipine", "dosage": "5mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "amlodipine", "dosage": "5mg", "frequency": "twice daily"},
        ]),
    ]),

    # P005 — missing medication conflict only (lisinopril missing from patient report)
    ("P005", [
        ("clinic_emr", [
            {"name": "ramipril", "dosage": "5mg", "frequency": "once daily"},
            {"name": "simvastatin", "dosage": "40mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "ramipril", "dosage": "5mg", "frequency": "once daily"},
            # simvastatin missing — triggers missing_medication conflict
        ]),
    ]),

    # P006 — drug interaction: aspirin + ibuprofen (high severity per rules)
    ("P006", [
        ("clinic_emr", [
            {"name": "aspirin", "dosage": "75mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "ibuprofen", "dosage": "400mg", "frequency": "three times daily"},
        ]),
    ]),

    # P007 — drug interaction: paracetamol + alcohol (medium severity)
    ("P007", [
        ("clinic_emr", [
            {"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"},
        ]),
        ("patient_reported", [
            {"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "occasionally"},
        ]),
    ]),

    # P008 — drug interaction: metformin + alcohol (high severity)
    ("P008", [
        ("clinic_emr", [
            {"name": "metformin", "dosage": "500mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "metformin", "dosage": "500mg", "frequency": "once daily"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "daily"},
        ]),
    ]),


    # ── EDGE CASES ──────────────────────────────────────────────────────────

    # P009 — three-way dosage conflict: all 3 sources report different doses
    ("P009", [
        ("clinic_emr", [
            {"name": "prednisolone", "dosage": "5mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "prednisolone", "dosage": "10mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "prednisolone", "dosage": "20mg", "frequency": "once daily"},
        ]),
    ]),

    # P010 — dosage AND frequency conflict on same drug simultaneously
    ("P010", [
        ("clinic_emr", [
            {"name": "sertraline", "dosage": "50mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "sertraline", "dosage": "100mg", "frequency": "twice daily"},
        ]),
    ]),

    # P011 — multiple conflict types on one patient:
    #         dosage conflict (warfarin) + missing med (bisoprolol) + drug interaction
    ("P011", [
        ("clinic_emr", [
            {"name": "warfarin", "dosage": "2mg", "frequency": "once daily"},
            {"name": "bisoprolol", "dosage": "5mg", "frequency": "once daily"},
            {"name": "aspirin", "dosage": "75mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "warfarin", "dosage": "5mg", "frequency": "once daily"},
            {"name": "ibuprofen", "dosage": "400mg", "frequency": "twice daily"},
            # bisoprolol missing → missing_medication conflict
            # aspirin + ibuprofen → drug_interaction conflict
        ]),
        ("patient_reported", [
            {"name": "warfarin", "dosage": "2mg", "frequency": "once daily"},
            {"name": "bisoprolol", "dosage": "2.5mg", "frequency": "once daily"},
            # bisoprolol dosage disagrees with clinic_emr → dosage_conflict
        ]),
    ]),

    # P012 — missing med AND drug interaction on same patient
    ("P012", [
        ("clinic_emr", [
            {"name": "metformin", "dosage": "850mg", "frequency": "twice daily"},
            {"name": "gliclazide", "dosage": "80mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "metformin", "dosage": "850mg", "frequency": "twice daily"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "weekends"},
            # gliclazide missing → missing_medication conflict
            # metformin + alcohol → drug_interaction conflict
        ]),
    ]),

    # P013 — medication with missing dosage field (empty string)
    #         tests normalization robustness — should not crash conflict detection
    ("P013", [
        ("clinic_emr", [
            {"name": "lisinopril", "dosage": "", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "lisinopril", "dosage": "10mg", "frequency": "once daily"},
        ]),
    ]),

    # P014 — medication with missing frequency field (empty string)
    ("P014", [
        ("clinic_emr", [
            {"name": "atorvastatin", "dosage": "20mg", "frequency": ""},
        ]),
        ("hospital_discharge", [
            {"name": "atorvastatin", "dosage": "20mg", "frequency": "once daily"},
        ]),
    ]),

    # P015 — case sensitivity edge case: drug name in mixed case
    #         normalize_dosage/name should lowercase "MeTfOrMiN" → "metformin"
    ("P015", [
        ("clinic_emr", [
            {"name": "MeTfOrMiN", "dosage": "500MG", "frequency": "Twice Daily"},
        ]),
        ("hospital_discharge", [
            {"name": "metformin", "dosage": "1000mg", "frequency": "once daily"},
        ]),
    ]),

    # P016 — whitespace edge case: "  aspirin  " should normalize to "aspirin"
    #         and match against the ibuprofen interaction rule
    ("P016", [
        ("clinic_emr", [
            {"name": "  aspirin  ", "dosage": "75mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "ibuprofen", "dosage": "400mg", "frequency": "twice daily"},
        ]),
    ]),

    # P017 — same drug, same dose, same frequency across 2 sources — no conflict
    #         (duplicate entries should NOT generate false positive conflicts)
    ("P017", [
        ("clinic_emr", [
            {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
        ]),
    ]),

    # P018 — dosage units edge case: 500mg vs 0.5g (same dose, different notation)
    #         currently NOT normalized — intentionally seeds this to document the
    #         limitation: system will flag this as a dosage_conflict even though
    #         clinically they are identical
    ("P018", [
        ("clinic_emr", [
            {"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"},
        ]),
        ("hospital_discharge", [
            {"name": "paracetamol", "dosage": "0.5g", "frequency": "four times daily"},
        ]),
    ]),

    # P019 — patient with a pre-resolved conflict seeded directly
    #         tests that resolved conflicts don't get re-created as active
    #         (conflict_storage skips if active record already exists,
    #          but resolved ones should allow re-detection if drug changes)
    ("P019", [
        ("clinic_emr", [
            {"name": "metoprolol", "dosage": "50mg", "frequency": "twice daily"},
            {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "metoprolol", "dosage": "50mg", "frequency": "twice daily"},
            {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
        ]),
    ]),

    # P020 — heavy multi-conflict patient: dosage + frequency + missing + interaction
    #         aspirin dosage conflict + ibuprofen interaction + paracetamol missing
    ("P020", [
        ("clinic_emr", [
            {"name": "aspirin", "dosage": "75mg", "frequency": "once daily"},
            {"name": "ibuprofen", "dosage": "400mg", "frequency": "three times daily"},
            {"name": "paracetamol", "dosage": "1000mg", "frequency": "four times daily"},
        ]),
        ("hospital_discharge", [
            {"name": "aspirin", "dosage": "150mg", "frequency": "once daily"},
            # paracetamol missing → missing_medication conflict
            # aspirin + ibuprofen → drug_interaction conflict
        ]),
        ("patient_reported", [
            {"name": "ibuprofen", "dosage": "200mg", "frequency": "as needed"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "daily"},
            # ibuprofen frequency conflict (3x daily vs as needed)
            # paracetamol + alcohol → drug_interaction (paracetamol in clinic, alcohol here)
        ]),
    ]),
]


# ─────────────────────────────────────────────
# PRE-RESOLVED CONFLICT for P019
# Seeded directly so we can test the resolved status path
# ─────────────────────────────────────────────

RESOLVED_CONFLICTS = [
    {
        "patient_id": "P019",
        "medication_name": "metoprolol",
        "conflict_type": "dosage_conflict",
        "entries": [
            {"source": "clinic_emr", "dosage": "25mg", "frequency": "twice daily", "timestamp": datetime.utcnow() - timedelta(days=10)},
            {"source": "hospital_discharge", "dosage": "50mg", "frequency": "twice daily", "timestamp": datetime.utcnow() - timedelta(days=10)},
        ],
        "severity": "medium",
        "description": "Historical dosage conflict — resolved after clinician review.",
        "status": "resolved",
        "created_at": datetime.utcnow() - timedelta(days=10),
        "resolved_at": datetime.utcnow() - timedelta(days=8),
        "resolution_note": "Hospital discharge dose accepted as authoritative source.",
    }
]


async def clear_collections():
    await medication_collection.delete_many({})
    await conflict_collection.delete_many({})
    print("Cleared existing data.")


async def seed_medications():
    version_tracker = {}

    for patient_id, source_records in PATIENTS:
        for source, medications in source_records:
            version_tracker[patient_id] = version_tracker.get(patient_id, 0) + 1

            # Stagger timestamps so timeline looks realistic
            offset_days = random.randint(0, 25)
            timestamp = datetime.utcnow() - timedelta(days=offset_days)

            doc = {
                "patient_id": patient_id,
                "source": source,
                "medications": medications,
                "timestamp": timestamp,
                "version": version_tracker[patient_id]
            }

            await medication_collection.insert_one(doc)

    print(f"Inserted medication records for {len(PATIENTS)} patients.")


async def seed_resolved_conflicts():
    for conflict in RESOLVED_CONFLICTS:
        await conflict_collection.insert_one(conflict)
    print(f"Inserted {len(RESOLVED_CONFLICTS)} pre-resolved conflict(s).")


async def seed_conflicts():
    """
    Run conflict detection for every patient and store results.
    Reuses the same logic as the API endpoint.
    """
    from app.service.conflict_detection import detect_conflicts
    from app.service.conflict_storage import store_conflicts

    total_conflicts = 0

    for patient_id, _ in PATIENTS:
        records = []
        async for doc in medication_collection.find({"patient_id": patient_id}):
            doc["_id"] = str(doc["_id"])
            records.append(doc)

        conflicts = detect_conflicts(records)
        await store_conflicts(patient_id, conflicts)
        total_conflicts += len(conflicts)

        print(f"  {patient_id}: {len(conflicts)} conflict(s) detected")

    print(f"\nTotal conflicts stored: {total_conflicts}")


async def main():
    print("Seeding medication reconciliation database...\n")
    await clear_collections()
    await seed_medications()
    print("\nInserting pre-resolved conflicts...")
    await seed_resolved_conflicts()
    print("\nRunning conflict detection...\n")
    await seed_conflicts()
    print("\nDone. Database is ready.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
