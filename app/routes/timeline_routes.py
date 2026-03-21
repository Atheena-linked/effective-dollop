from fastapi import APIRouter
from app.config.database import conflict_collection, medication_collection
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/patients/high-conflicts")
async def get_patients_with_high_conflicts():
    """Return all patients with >= 1 unresolved (active) conflict."""
    pipeline = [
        {"$match": {"status": "active"}},
        {
            "$group": {
                "_id": "$patient_id",
                "conflict_count": {"$sum": 1}
            }
        },
        {"$match": {"conflict_count": {"$gt": 1}}}
    ]

    results = []
    async for doc in conflict_collection.aggregate(pipeline):
        results.append({
            "patient_id": doc["_id"],
            "conflict_count": doc["conflict_count"]
        })

    return {"patients": results}


@router.get("/patients/{patient_id}/timeline")
async def get_timeline(patient_id: str):
    cursor = medication_collection.find(
        {"patient_id": patient_id}
    ).sort("timestamp", 1)

    timeline = []

    async for doc in cursor:
        doc["_id"] = str(doc["_id"])

        timeline.append({
            "version": doc.get("version"),
            "timestamp": doc.get("timestamp"),
            "source": doc.get("source"),
            "medications": doc.get("medications")
        })

    return {
        "patient_id": patient_id,
        "timeline": timeline
    }


@router.get("/patients/{patient_id}/timeline/{version}")
async def get_specific_version(patient_id: str, version: int):
    doc = await medication_collection.find_one({
        "patient_id": patient_id,
        "version": version
    })
    if not doc:
        return {"error": "Version not found"}

    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/patients/{patient_id}/timeline/diff/{v1}/{v2}")
async def diff_versions(patient_id: str, v1: int, v2: int):
    doc1 = await medication_collection.find_one({"patient_id": patient_id, "version": v1})
    doc2 = await medication_collection.find_one({"patient_id": patient_id, "version": v2})

    if not doc1:
        return {"error": f"version {v1} not found"}
    if not doc2:
        return {"error": f"version {v2} not found"}

    meds1 = {m["name"].lower() for m in doc1.get("medications", [])}
    meds2 = {m["name"].lower() for m in doc2.get("medications", [])}

    return {
        "patient_id": patient_id,
        "from_version": v1,
        "to_version": v2,
        "added": list(meds2 - meds1),
        "removed": list(meds1 - meds2),
        "unchanged": list(meds1 & meds2)
    }


@router.get("/analytics/conflicts-per-clinic")
async def conflicts_per_clinic():
    """
    For the past 30 days, count patients with >= 2 conflicts per source clinic.
    Uses 'source' stored on each conflict entry.
    """
    last_30_days = datetime.utcnow() - timedelta(days=30)

    pipeline = [
        {"$match": {"created_at": {"$gte": last_30_days}}},
        {
            "$unwind": "$entries"
        },
        {
            "$group": {
                "_id": {
                    "clinic": "$entries.source",
                    "patient": "$patient_id"
                },
                "conflict_count": {"$sum": 1}
            }
        },
        {"$match": {"conflict_count": {"$gte": 2}}},
        {
            "$group": {
                "_id": "$_id.clinic",
                "patients_with_multiple_conflicts": {"$sum": 1}
            }
        }
    ]

    result = []
    async for doc in conflict_collection.aggregate(pipeline):
        result.append({
            "clinic": doc["_id"],
            "patients_with_multiple_conflicts": doc["patients_with_multiple_conflicts"]
        })

    return {"clinics": result}
