import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Uuid
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BaseModel(Base):
    """
    Abstract base model that includes UUID primary key and created_at/updated_at timestamps.
    """
    __abstract__ = True
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
