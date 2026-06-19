from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models.complaint import SeverityEnum, StatusEnum

class CrisisBase(BaseModel):
    title: str
    description: str | None = None
    severity: SeverityEnum = SeverityEnum.low
    location: str
    status: StatusEnum = StatusEnum.active

class CrisisCreate(CrisisBase):
    pass

class CrisisUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: SeverityEnum | None = None
    location: str | None = None
    status: StatusEnum | None = None

class CrisisInDBBase(CrisisBase):
    id: int
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Complaint(CrisisInDBBase):
    pass
