from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from .base import BaseModel

class Agent(BaseModel):
    __tablename__ = "agents"

    name = Column(String, index=True, nullable=False)
    type = Column(String, index=True, nullable=False)
    status = Column(String, index=True, nullable=False)

    # Relationships
    assignments = relationship("Assignment", back_populates="agent", cascade="all, delete-orphan")
    incidents = relationship("Incident", secondary="assignments", back_populates="agents", viewonly=True)
