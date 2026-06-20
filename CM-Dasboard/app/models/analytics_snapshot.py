from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel

class AnalyticsSnapshot(BaseModel):
    __tablename__ = "analytics_snapshot"

    key: Mapped[str] = mapped_column(String(50), default="analytics_snapshot", unique=True, index=True, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
