from fastapi import APIRouter
from app.config.database import medication_collection   
from app.service.conflict_detection import detect_conflicts

router = APIRouter()

@router.get("/conflicts/{patient_id}")
async def get_conflicts(patient_id: str ):

    records = []
    
    cursor = medication_collection.find({"patient_id":patient_id})

    async for doc in cursor:
        doc["_id"] =  str(doc["_id"])
        records.append(doc)

    conflicts = detect_conflicts(records)

    return {
        "patient_id":patient_id,
        "conflicts": conflicts
    }