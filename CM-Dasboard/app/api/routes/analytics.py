from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import AnalyticsSnapshotResponse
from app.services.analytics import AnalyticsSnapshotService

router = APIRouter()

@router.get("/snapshot", response_model=AnalyticsSnapshotResponse)
async def get_analytics_snapshot(db: AsyncSession = Depends(get_db)):
    """
    Fetch the latest analytics snapshot from Redis (optional) or Postgres database.
    No authentication required.
    """
    snapshot = await AnalyticsSnapshotService.get_snapshot(db)
    return snapshot
