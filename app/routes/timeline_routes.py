from fastapi import APIRouter
from app.config.database import conflict_collection
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