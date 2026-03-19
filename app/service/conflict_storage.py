from datetime import datetime
from app.config.database import conflict_collection

async def store_conflicts(patient_id: str, conflicts: list):

    for conflict in conflicts:

        existing = await conflict_collection.find_one({
            "patient_id": patient_id,
            "medication_name": conflict["medication_name"],
            "status": "active"
        })

        if not existing:
            conflict_doc = {
                **conflict,
                "patient_id": patient_id,
                "status": "active",
                "created_at": datetime.utcnow(),
                "resolved_at": None,
                "resolution_note": None
            }

            await conflict_collection.insert_one(conflict_doc)