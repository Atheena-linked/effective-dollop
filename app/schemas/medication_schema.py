from pydantic import BaseModel
from typing import List

class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str

class MedicationRecord(BaseModel):
    patient_id: str
    source: str
    medications: List[Medication]