"""
Seed script — generates 15 patients with varied medication conflicts.
Run from the project root:
    python seed.py
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

# --- Patient medication data ---
# Each patient is a list of (source, medications) tuples
# Conflicts are intentionally seeded: dose mismatches, missing meds, interactions

PATIENTS = [
    # P001 — dosage conflict on metformin, missing lisinopril in patient report
    ("P001", [
        ("clinic_emr", [
            {"name": "metformin", "dosage": "500mg", "frequency": "twice daily"},
            {"name": "lisinopril", "dosage": "10mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "metformin", "dosage": "1000mg", "frequency": "once daily"},
            {"name": "lisinopril", "dosage": "10mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "metformin", "dosage": "500mg", "frequency": "twice daily"},
        ]),
    ]),

    # P002 — drug interaction: aspirin + ibuprofen
    ("P002", [
        ("clinic_emr", [
            {"name": "aspirin", "dosage": "75mg", "frequency": "once daily"},
            {"name": "atorvastatin", "dosage": "20mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "ibuprofen", "dosage": "400mg", "frequency": "three times daily"},
            {"name": "atorvastatin", "dosage": "20mg", "frequency": "once daily"},
        ]),
    ]),

    # P003 — frequency conflict on amlodipine
    ("P003", [
        ("clinic_emr", [
            {"name": "amlodipine", "dosage": "5mg", "frequency": "once daily"},
            {"name": "omeprazole", "dosage": "20mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "amlodipine", "dosage": "5mg", "frequency": "twice daily"},
            {"name": "omeprazole", "dosage": "20mg", "frequency": "once daily"},
        ]),
    ]),

    # P004 — metformin + alcohol interaction (patient reported alcohol)
    ("P004", [
        ("clinic_emr", [
            {"name": "metformin", "dosage": "500mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "metformin", "dosage": "500mg", "frequency": "once daily"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "daily"},
        ]),
    ]),

    # P005 — clean patient, no conflicts
    ("P005", [
        ("clinic_emr", [
            {"name": "levothyroxine", "dosage": "50mcg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "levothyroxine", "dosage": "50mcg", "frequency": "once daily"},
        ]),
    ]),

    # P006 — multiple conflicts: dosage + missing med
    ("P006", [
        ("clinic_emr", [
            {"name": "warfarin", "dosage": "2mg", "frequency": "once daily"},
            {"name": "bisoprolol", "dosage": "5mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "warfarin", "dosage": "5mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "warfarin", "dosage": "2mg", "frequency": "once daily"},
            {"name": "bisoprolol", "dosage": "2.5mg", "frequency": "once daily"},
        ]),
    ]),

    # P007 — paracetamol + alcohol interaction
    ("P007", [
        ("clinic_emr", [
            {"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"},
            {"name": "codeine", "dosage": "30mg", "frequency": "four times daily"},
        ]),
        ("patient_reported", [
            {"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "occasionally"},
        ]),
    ]),

    # P008 — missing medication conflict only
    ("P008", [
        ("clinic_emr", [
            {"name": "ramipril", "dosage": "5mg", "frequency": "once daily"},
            {"name": "simvastatin", "dosage": "40mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "ramipril", "dosage": "5mg", "frequency": "once daily"},
        ]),
    ]),

    # P009 — aspirin + ibuprofen interaction again, different dose conflict too
    ("P009", [
        ("clinic_emr", [
            {"name": "aspirin", "dosage": "100mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "aspirin", "dosage": "75mg", "frequency": "once daily"},
            {"name": "ibuprofen", "dosage": "200mg", "frequency": "twice daily"},
        ]),
    ]),

    # P010 — clean patient
    ("P010", [
        ("clinic_emr", [
            {"name": "metoprolol", "dosage": "50mg", "frequency": "twice daily"},
            {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "metoprolol", "dosage": "50mg", "frequency": "twice daily"},
            {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
        ]),
    ]),

    # P011 — three-way dosage conflict
    ("P011", [
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

    # P012 — frequency + missing conflict
    ("P012", [
        ("clinic_emr", [
            {"name": "sertraline", "dosage": "50mg", "frequency": "once daily"},
            {"name": "quetiapine", "dosage": "25mg", "frequency": "at night"},
        ]),
        ("hospital_discharge", [
            {"name": "sertraline", "dosage": "50mg", "frequency": "twice daily"},
        ]),
    ]),

    # P013 — metformin + alcohol, plus dosage conflict
    ("P013", [
        ("clinic_emr", [
            {"name": "metformin", "dosage": "850mg", "frequency": "twice daily"},
            {"name": "gliclazide", "dosage": "80mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "metformin", "dosage": "500mg", "frequency": "twice daily"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "weekends"},
        ]),
    ]),

    # P014 — clean patient, all sources agree
    ("P014", [
        ("clinic_emr", [
            {"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"},
        ]),
        ("hospital_discharge", [
            {"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"},
        ]),
        ("patient_reported", [
            {"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"},
        ]),
    ]),

    # P015 — multiple conflicts across all three sources
    ("P015", [
        ("clinic_emr", [
            {"name": "aspirin", "dosage": "75mg", "frequency": "once daily"},
            {"name": "ibuprofen", "dosage": "400mg", "frequency": "three times daily"},
            {"name": "paracetamol", "dosage": "1000mg", "frequency": "four times daily"},
        ]),
        ("hospital_discharge", [
            {"name": "aspirin", "dosage": "150mg", "frequency": "once daily"},
            {"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"},
        ]),
        ("patient_reported", [
            {"name": "ibuprofen", "dosage": "200mg", "frequency": "as needed"},
            {"name": "alcohol", "dosage": "n/a", "frequency": "daily"},
        ]),
    ]),
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
    print("\nRunning conflict detection...\n")
    await seed_conflicts()
    print("\nDone. Database is ready.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
