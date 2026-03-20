from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config.database import medication_collection, conflict_collection
from app.service.conflict_detection import detect_conflicts
from app.service.conflict_storage import store_conflicts
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId

router = APIRouter()


class ResolveRequest(BaseModel):
    resolution_note: str
    resolved_by_source: str = None


@router.post("/conflicts_detect_and_store/{patient_id}")
async def detect_and_store_conflicts(patient_id: str):
    records = []
    async for doc in medication_collection.find({"patient_id": patient_id}):
        doc["_id"] = str(doc["_id"])
        records.append(doc)

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
    query = {"patient_id": patient_id}
    if status:
        query["status"] = status

    conflicts = []
    async for doc in conflict_collection.find(query):
        doc["_id"] = str(doc["_id"])
        conflicts.append(doc)

    return conflicts


@router.patch("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, body: ResolveRequest):
    """Mark a conflict resolved with an audit trail."""
    try:
        oid = ObjectId(conflict_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid conflict ID format")

    result = await conflict_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.utcnow(),
                "resolution_note": body.resolution_note,
                "resolved_by_source": body.resolved_by_source
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conflict not found")

    return {"message": "Conflict marked as resolved", "conflict_id": conflict_id}