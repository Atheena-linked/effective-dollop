from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ConflictEntry(BaseModel):
    source: str
    dosage: str
    frequency: str
    timestamp: datetime


class Conflict(BaseModel):
    patient_id: str
    medication_name: str
    conflict_type: str
    entries: List[ConflictEntry]

    status: str = "active"
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None