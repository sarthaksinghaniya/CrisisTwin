from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class AssignmentBase(BaseModel):
    agent_id: UUID
    incident_id: UUID

class AssignmentCreate(AssignmentBase):
    pass

class AssignmentUpdate(BaseModel):
    # assignments usually don't need update, but if they do, maybe switch agent
    agent_id: UUID

class AssignmentResponse(AssignmentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
