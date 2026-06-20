import uuid
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional

class TimelineEventResponse(BaseModel):
    status: str
    timestamp: datetime
    relative_time: str
    updated_by: str
    color: str
    proof_urls: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class TimelineResponse(BaseModel):
    ticket_id: str
    current_status: str
    comment_count: int
    feedback_submitted: bool
    feedback_rating: Optional[int] = None
    feedback_remarks: Optional[str] = None
    timeline: List[TimelineEventResponse]

    model_config = ConfigDict(from_attributes=True)
