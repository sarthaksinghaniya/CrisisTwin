from typing import Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ReportBase(BaseModel):
    incident_id: UUID
    content: str
    created_by: UUID

class ReportCreate(ReportBase):
    pass

class ReportUpdate(BaseModel):
    content: Optional[str] = None

class ReportResponse(ReportBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
