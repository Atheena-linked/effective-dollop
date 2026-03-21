from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config.database import medication_collection, conflict_collection
from app.service.conflict_detection import detect_conflicts
from app.service.conflict_storage import store_conflicts
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from app.service.conflict_resolution import score_candidates

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


@router.patch("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, body: ResolveRequest):
    """Mark a conflict resolved manually with an audit trail."""
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


@router.post("/conflicts/{conflict_id}/resolve/smart")
async def smart_resolve_conflict(conflict_id: str):
    """
    Score-based automatic resolution.

    Scores every reported (dosage, frequency) candidate for the
    conflicting medication using:
        score = source_priority + appearance_count + recency_bonus

    The highest-scoring candidate is chosen and the conflict is marked
    resolved with a full scoring breakdown stored as the resolution note.
    """
    # 1. Fetch the conflict document
    try:
        oid = ObjectId(conflict_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid conflict ID format")

    conflict = await conflict_collection.find_one({"_id": oid})
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")

    if conflict.get("status") == "resolved":
        raise HTTPException(status_code=400, detail="Conflict is already resolved")

    patient_id = conflict["patient_id"]
    med_name = conflict["medication_name"]

    conflict_type = conflict.get("conflict_type")
    if conflict_type == "drug_interaction":
        raise HTTPException(
            status_code=400,
            detail="Drug interaction conflicts cannot be auto-resolved by scoring. "
                   "Use the manual resolve endpoint with a clinician note."
        )

    # 2. Fetch all medication records for this patient
    records = []
    async for doc in medication_collection.find({"patient_id": patient_id}):
        doc["_id"] = str(doc["_id"])
        records.append(doc)

    if not records:
        raise HTTPException(status_code=404, detail="No medication records found for patient")

    # 3. Run scoring algorithm
    result = score_candidates(med_name, records)

    if not result:
        raise HTTPException(
            status_code=422,
            detail=f"Could not score candidates for medication '{med_name}'"
        )

    winner = result["winner"]

    # 4. Mark conflict as resolved with full scoring audit trail
    resolution_note = result["scoring_breakdown"]

    await conflict_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.utcnow(),
                "resolution_note": resolution_note,
                "resolved_by_source": ", ".join(winner["supporting_sources"]),
                "resolved_value": {
                    "dosage": winner["dosage"],
                    "frequency": winner["frequency"],
                    "score": winner["score"],
                    "supporting_sources": winner["supporting_sources"],
                    "all_scores": result["all_scores"]
                }
            }
        }
    )

    return {
        "message": "Conflict resolved using score-based algorithm",
        "conflict_id": conflict_id,
        "medication": med_name,
        "resolved_value": {
            "dosage": winner["dosage"],
            "frequency": winner["frequency"]
        },
        "score": winner["score"],
        "breakdown": winner["breakdown"],
        "supporting_sources": winner["supporting_sources"],
        "all_candidates": result["all_scores"],
        "resolution_note": resolution_note
    }
