from pydantic import BaseModel, field_validator
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

    @field_validator("medications")
    @classmethod
    def medications_not_empty(cls, v):
        if not v:
            raise ValueError("medications list cannot be empty")
        return v
    
    timestamp: Optional[datetime] = None
    version: Optional[int] = None