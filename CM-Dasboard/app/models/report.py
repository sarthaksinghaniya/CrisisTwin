from sqlalchemy import Column, Text, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from .base import BaseModel

class Report(BaseModel):
    __tablename__ = "reports"

    incident_id = Column(Uuid, ForeignKey("incidents.id"), index=True, nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id"), index=True, nullable=False)

    # Relationships
    incident = relationship("Incident", back_populates="reports")
    creator = relationship("User")
