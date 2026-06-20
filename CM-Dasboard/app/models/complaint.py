import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Text, Enum, ForeignKey, Integer, Float, DateTime, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel

class PriorityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"
    FAILED_FINAL = "FAILED_FINAL"

class Complaint(BaseModel):
    __tablename__ = "complaints"
    
    __table_args__ = (
        Index("ix_complaint_status_time", "status", "updated_at"),
    )

    ticket_id: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    citizen_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    citizen_email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    citizen_phone: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    
    # Geographic location
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Enums
    priority: Mapped[PriorityEnum] = mapped_column(Enum(PriorityEnum), default=PriorityEnum.LOW, index=True, nullable=False)
    status: Mapped[ComplaintStatus] = mapped_column(Enum(ComplaintStatus), default=ComplaintStatus.SUBMITTED, index=True, nullable=False)
    
    # Assigned Officer FK
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    # Retry Tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    assigned_officer: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_complaints",
        foreign_keys=[assigned_to]
    )
    updates: Mapped[List["ComplaintUpdate"]] = relationship(
        "ComplaintUpdate",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
    attachments: Mapped[List["Attachment"]] = relationship(
        "Attachment",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        "Feedback",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
    escalations: Mapped[List["Escalation"]] = relationship(
        "Escalation",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
