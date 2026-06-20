import pytest
import os
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.user import User, RoleEnum
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.services.analytics import AnalyticsSnapshotService

# Mock Redis class for storage testing
class MockRedis:
    def __init__(self, should_fail=False, db_store=None):
        self.should_fail = should_fail
        self.db = db_store if db_store is not None else {}

    async def __aenter__(self):
        if self.should_fail:
            raise Exception("Redis connection failed")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def set(self, key, val, **kwargs):
        if self.should_fail:
            raise Exception("Redis write failed")
        self.db[key] = val

    async def get(self, key):
        if self.should_fail:
            raise Exception("Redis read failed")
        return self.db.get(key)

import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def clean_db(db_session: AsyncSession):
    # Clear tables before each test
    from app.models.complaint import Complaint
    from app.models.user import User
    from app.models.analytics_snapshot import AnalyticsSnapshot
    
    await db_session.execute(Complaint.__table__.delete())
    await db_session.execute(User.__table__.delete())
    await db_session.execute(AnalyticsSnapshot.__table__.delete())
    await db_session.commit()

@pytest.mark.asyncio
async def test_compute_snapshot_success(db_session: AsyncSession, create_test_user):
    # 1. Setup users/officers
    officer = await create_test_user(
        email="officer1_analytics@example.com",
        role=RoleEnum.OFFICER,
        name="Officer Vikram"
    )
    
    # 2. Setup standard resolved and pending complaints
    c1 = Complaint(
        ticket_id="DL-2026-ANLYT1",
        citizen_name="Aman",
        title="Sanitation Issue",
        category="SANITATION",
        department="MCD",
        district="South Delhi",
        priority=PriorityEnum.CRITICAL, # 24 hours SLA
        status=ComplaintStatus.RESOLVED,
        assigned_to=officer.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=10),
        updated_at=datetime.now(timezone.utc) # resolution time = 10 hours
    )
    
    c2 = Complaint(
        ticket_id="DL-2026-ANLYT2",
        citizen_name="Rahul",
        title="Water Leaking",
        category="WATER",
        department="DJB",
        district="West Delhi",
        priority=PriorityEnum.MEDIUM, # 168 hours SLA
        status=ComplaintStatus.SUBMITTED,
        created_at=datetime.now(timezone.utc)
    )
    
    db_session.add_all([c1, c2])
    await db_session.commit()
    
    # 3. Compute Snapshot
    snapshot = await AnalyticsSnapshotService.compute_snapshot(db_session)
    
    assert snapshot["total_complaints"] == 2
    assert snapshot["pending"] == 1
    assert snapshot["resolved"] == 1
    assert snapshot["average_sla"] == round((24 + 168) / 2.0, 2)
    assert snapshot["average_resolution_time"] == 10.0
    
    assert snapshot["top_departments"]["MCD"] == 1
    assert snapshot["top_departments"]["DJB"] == 1
    assert snapshot["top_districts"]["South Delhi"] == 1
    assert snapshot["top_districts"]["West Delhi"] == 1
    assert snapshot["top_categories"]["SANITATION"] == 1
    assert snapshot["top_categories"]["WATER"] == 1
    
    assert len(snapshot["officer_ranking"]) == 1
    assert snapshot["officer_ranking"][0]["officer_name"] == "Officer Vikram"
    assert snapshot["officer_ranking"][0]["resolved_count"] == 1

@pytest.mark.asyncio
async def test_compute_snapshot_edge_case_empty(db_session: AsyncSession):
    # Test computing metrics when database has 0 complaints
    snapshot = await AnalyticsSnapshotService.compute_snapshot(db_session)
    
    assert snapshot["total_complaints"] == 0
    assert snapshot["pending"] == 0
    assert snapshot["resolved"] == 0
    assert snapshot["average_sla"] == 0.0
    assert snapshot["average_resolution_time"] == 0.0
    assert snapshot["top_departments"] == {}
    assert snapshot["top_districts"] == {}
    assert snapshot["top_categories"] == {}
    assert snapshot["officer_ranking"] == []

@pytest.mark.asyncio
async def test_compute_snapshot_edge_case_missing_district_and_neg_duration(db_session: AsyncSession):
    # Setup complaint with missing district and negative duration
    c = Complaint(
        ticket_id="DL-2026-EDGE99",
        citizen_name="Citizen Edge",
        title="Pothole",
        category="ROAD",
        department="PWD",
        district="   ", # Missing district
        priority=PriorityEnum.LOW, # 336 hours SLA
        status=ComplaintStatus.RESOLVED,
        created_at=datetime.now(timezone.utc) + timedelta(hours=5), # Future created_at
        updated_at=datetime.now(timezone.utc) # Past updated_at -> Negative duration!
    )
    
    db_session.add(c)
    await db_session.commit()
    
    snapshot = await AnalyticsSnapshotService.compute_snapshot(db_session)
    
    # Missing district should map to "Unknown"
    assert "Unknown" in snapshot["top_districts"]
    assert snapshot["top_districts"]["Unknown"] == 1
    
    # Negative resolution duration should clamp to 0.0
    assert snapshot["average_resolution_time"] == 0.0

@pytest.mark.asyncio
async def test_storage_fallback_redis_vs_postgres(db_session: AsyncSession):
    snapshot_test = {
        "timestamp": "2026-06-20T21:00:00Z",
        "total_complaints": 5,
        "pending": 2,
        "resolved": 3,
        "escalated": 0,
        "average_sla": 100.0,
        "average_resolution_time": 4.5,
        "top_departments": {"MCD": 5},
        "top_districts": {"South": 5},
        "top_categories": {"SANITATION": 5},
        "officer_ranking": []
    }
    
    # 1. Test save when Redis is online
    mock_store = {}
    with patch("redis.asyncio.from_url", return_value=MockRedis(should_fail=False, db_store=mock_store)):
        await AnalyticsSnapshotService.save_snapshot(snapshot_test, db_session)
        
        # Verify stored in Redis
        assert "analytics_snapshot" in mock_store
        assert json.loads(mock_store["analytics_snapshot"])["total_complaints"] == 5
        
    # 2. Test save when Redis fails (Postgres fallback should write it to database)
    # Clear DB table first
    await db_session.execute(select(AnalyticsSnapshot).filter(AnalyticsSnapshot.key == "analytics_snapshot"))
    with patch("redis.asyncio.from_url", return_value=MockRedis(should_fail=True)):
        await AnalyticsSnapshotService.save_snapshot(snapshot_test, db_session)
        
        # Verify written to Postgres fallback
        stmt = select(AnalyticsSnapshot).filter(AnalyticsSnapshot.key == "analytics_snapshot")
        res = await db_session.execute(stmt)
        record = res.scalars().first()
        assert record is not None
        assert record.data["total_complaints"] == 5
        
    # 3. Test get when Redis is offline (should fall back to retrieve from Postgres)
    with patch("redis.asyncio.from_url", return_value=MockRedis(should_fail=True)):
        snapshot_get = await AnalyticsSnapshotService.get_snapshot(db_session)
        assert snapshot_get["total_complaints"] == 5

@pytest.mark.asyncio
async def test_get_analytics_snapshot_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    snapshot_test = {
        "timestamp": "2026-06-20T21:00:00Z",
        "total_complaints": 12,
        "pending": 5,
        "resolved": 7,
        "escalated": 1,
        "average_sla": 120.0,
        "average_resolution_time": 6.8,
        "top_departments": {"MCD": 12},
        "top_districts": {"South": 12},
        "top_categories": {"SANITATION": 12},
        "officer_ranking": []
    }
    
    # Save snapshot in database for Postgres fallback retrieval
    stmt = select(AnalyticsSnapshot).filter(AnalyticsSnapshot.key == "analytics_snapshot")
    res = await db_session.execute(stmt)
    record = res.scalars().first()
    if record:
        record.data = snapshot_test
    else:
        record = AnalyticsSnapshot(key="analytics_snapshot", data=snapshot_test)
        db_session.add(record)
    await db_session.commit()
    
    # Query endpoint
    # Patch Redis to fail so it falls back to Postgres
    with patch("redis.asyncio.from_url", return_value=MockRedis(should_fail=True)):
        response = await async_client.get("/api/v1/analytics/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["total_complaints"] == 12
        assert data["pending"] == 5
        assert data["average_sla"] == 120.0

def test_celery_task_execution():
    from app.tasks.analytics import run_analytics_snapshot_job
    # Simply patch compute_snapshot and save_snapshot to verify trigger logic does not throw exceptions
    with patch("app.services.analytics.AnalyticsSnapshotService.compute_snapshot", return_value={}) as mock_compute, \
         patch("app.services.analytics.AnalyticsSnapshotService.save_snapshot") as mock_save:
        run_analytics_snapshot_job()
        assert mock_compute.called
        assert mock_save.called
