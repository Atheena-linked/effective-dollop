from fastapi import APIRouter
from app.schemas.medication_schema import MedicationRecord
from app.config.database import medication_collection

router = APIRouter()

@router.post("/medications")
async def add_medication_record(record:MedicationRecord):
    await medication_collection.insert_one(record.model_dump())
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