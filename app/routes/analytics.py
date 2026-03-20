from fastapi import APIRouter
from app.config.database import conflict_collection

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