from pydantic import BaseModel
from typing import List,Optional
from datetime import datetime

class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str

class MedicationRecord(BaseModel):
    patient_id: str
    source: str
    medications: List[Medication]
    timestamp: Optional[datetime] = None
    version: Optional[int] = None