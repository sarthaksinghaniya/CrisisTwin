from typing import Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class AgentBase(BaseModel):
    name: str
    type: str
    status: str

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None

class AgentResponse(AgentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AgentAssignRequest(BaseModel):
    ticket_id: str


class AgentDecisionResponse(BaseModel):
    decision: str
    reasoning: str