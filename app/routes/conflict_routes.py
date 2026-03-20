from fastapi import APIRouter, HTTPException
from app.config.database import medication_collection , conflict_collection 
from app.service.conflict_detection import detect_conflicts
from app.service.conflict_storage import store_conflicts
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId


router = APIRouter()

@router.post("/conflicts_detect_and_store/{patient_id}")
async def detect_and_store_conflicts(patient_id: str ):
    """
    Run conflict detection across all medication records for a patient
    and persist any new conflicts found. Returns the full list of detected conflicts.
    """
    records = []
    
    cursor = medication_collection.find({"patient_id":patient_id})

    async for doc in cursor:
        print(doc)
        doc["_id"] =  str(doc["_id"])
        records.append(doc)
    print("TOTAL RECORDS:", len(records))

    if not records:
        raise HTTPException(status_code=404, detail="No medication records found for this patient")


    conflicts = detect_conflicts(records)

    await store_conflicts(patient_id, conflicts)

    return {
        "patient_id": patient_id,
        "total_conflicts": len(conflicts),
        "conflicts": conflicts
    }

@router.get("/conflicts/{patient_id}")
async def get_conflicts(patient_id: str, status: str = None):
    """
    Return all conflicts for a patient. Optionally filter by status
    using the ?status=active or ?status=resolved query parameter.
    """
    query = {"patient_id": patient_id}

    if status:
        query["status"] = status

    conflicts = []

    cursor = conflict_collection.find(query)

    async for doc in cursor:
        doc["_id"] = str(doc["_id"]) 
        
        conflicts.append(doc)

    return conflicts


@router.patch("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str):
    """Mark a conflict as resolved by its MongoDB ObjectId."""
    try:
        oid = ObjectId(conflict_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid conflict ID format")



    result = await conflict_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        return {"error": "Conflict not found"}
    
    return {
        "message": "Conflict marked as resolved",
        "conflict_id": conflict_id
    }