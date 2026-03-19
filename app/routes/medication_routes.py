from fastapi import APIRouter
from app.schemas.medication_schema import MedicationRecord
from app.config.database import medication_collection
from datetime import datetime
from app.utils.versioning import get_next_version

router = APIRouter()

@router.post("/medications")
async def add_medication_record(record:MedicationRecord):
    #Load the record  into data
    data = record.model_dump()

    data["timestamp"] = datetime.utcnow()

    data["version"] = await get_next_version(
        medication_collection,
        data["patient_id"]
    )
    await medication_collection.insert_one(data)    
    return {"message": "Record stored"}



@router.get("/medications/{patient_id}")
async def get_medication_records(patient_id: str):

    records = []

    cursor = medication_collection.find({"patient_id":patient_id})

    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        records.append(doc)

    return {
        "patient_id": patient_id,
        "records": records
    }