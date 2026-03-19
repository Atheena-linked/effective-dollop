from fastapi import APIRouter
from app.schemas.medication_schema import MedicationRecord
from app.config.database import medication_collection

router = APIRouter()

@router.post("/medications")
async def add_medication_record(record:MedicationRecord):
    await medication_collection.insert_one(record.model_dump())
    return {"message": "Record stored"}

