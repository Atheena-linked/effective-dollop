from fastapi import APIRouter
from app.config.database import medication_collection

router = APIRouter()


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