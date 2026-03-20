from fastapi import APIRouter
from app.config.database import conflict_collection
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/patients/high-conflicts")
async def get_patients_with_high_conflicts():

    pipeline = [
        {
            "$group": {
                "_id": "$patient_id",
                "conflict_count": {"$sum": 1}
            }
        },
        {
            "$match": {
                "conflict_count": {"$gt": 1}
            }
        }
    ]

    results = []

    cursor = conflict_collection.aggregate(pipeline)

    async for doc in cursor:
        results.append({
            "patient_id": doc["_id"],
            "conflict_count": doc["conflict_count"]
        })

    return {"patients": results}


@router.get("/analytics/conflicts-per-clinic")
async def conflicts_per_clinic():

    last_30_days = datetime.utcnow() - timedelta(days=30)


    pipeline = [
        {
            "$match": {
                "timestamp": {"$gte": last_30_days}
            }
        },
        {
            "$group": {
                "_id": {
                    "clinic": "$source",
                    "patient": "$patient_id"
                },
                "conflict_count": {"$sum": 1}
            }
        },
        {
            "$match": {
                "conflict_count": {"$gte": 2}
            }
        },
        {
            "$group": {
                "_id": "$_id.clinic",
                "patients_with_conflicts": {"$sum": 1}
            }
        }
    ]

    result = []

    cursor = conflict_collection.aggregate(pipeline)

    async for doc in cursor:
        result.append(doc)

    return result