from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from .base import BaseModel

class User(BaseModel):
    __tablename__ = "users"

    name = Column(String, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False)

    # Relationships
    incidents = relationship("Incident", back_populates="creator")
