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


@router.get("/patients/{patient_id}/timeline/diff/{v1}/{v2}")
async def diff_versions(patient_id: str, v1: int, v2: int):
    doc1 = await medication_collection.find_one({"patient_id": patient_id, "version": v1})
    doc2 = await medication_collection.find_one({"patient_id": patient_id, "version": v2})

    if not doc1 :
        return {"error": f"version {v1} not found"}
    if not doc2 :
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