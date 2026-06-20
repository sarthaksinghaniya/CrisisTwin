from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional, List
from app.models.complaint import PriorityEnum, ComplaintStatus

class ComplaintBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    department: str
    district: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    priority: PriorityEnum = PriorityEnum.LOW
    status: ComplaintStatus = ComplaintStatus.SUBMITTED

class CrisisCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    department: str
    district: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    priority: Optional[PriorityEnum] = PriorityEnum.LOW
    status: Optional[ComplaintStatus] = ComplaintStatus.SUBMITTED

class CrisisUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    priority: Optional[PriorityEnum] = None
    status: Optional[ComplaintStatus] = None

class Complaint(ComplaintBase):
    id: int
    ticket_id: str
    citizen_name: Optional[str] = None
    citizen_email: Optional[str] = None
    citizen_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ComplaintSubmissionResponse(BaseModel):
    ticket_id: str
    status: str
    estimated_sla: str
