from sqlalchemy import Column, String, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship
from .base import BaseModel

class Incident(BaseModel):
    __tablename__ = "incidents"

    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, index=True, nullable=False)
    status = Column(String, index=True, nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id"), nullable=False)

    # Relationships
    creator = relationship("User", back_populates="incidents")
    reports = relationship("Report", back_populates="incident", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="incident", cascade="all, delete-orphan")
    agents = relationship("Agent", secondary="assignments", back_populates="incidents", viewonly=True)
