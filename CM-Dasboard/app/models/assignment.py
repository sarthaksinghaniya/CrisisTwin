from sqlalchemy import Column, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from .base import BaseModel

class Assignment(BaseModel):
    __tablename__ = "assignments"

    agent_id = Column(Uuid, ForeignKey("agents.id"), index=True, nullable=False)
    incident_id = Column(Uuid, ForeignKey("incidents.id"), index=True, nullable=False)

    # Relationships
    agent = relationship("Agent", back_populates="assignments")
    incident = relationship("Incident", back_populates="assignments")
