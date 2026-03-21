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

    
class MedicationDocument(MedicationRecord):   
    timestamp: Optional[datetime] = None
    version: Optional[int] = None

    @field_validator("medications")
    @classmethod
    def medications_not_empty(cls, v):
        if not v:
            raise ValueError("medications list cannot be empty")
        return v

    @field_validator("patient_id")
    @classmethod
    def patient_id_not_blank(cls, v):
        if not v.strip():
            raise ValueError("patient_id cannot be blank")
        return v.strip()