import pytest
import json
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RoleEnum
from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.services.analytics import AnalyticsSnapshotService
from app.api.routes.analytics import _in_memory_cache

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

    async def setex(self, key, time_val, val):
        if self.should_fail:
            raise Exception("Redis write failed")
        self.db[key] = val

    async def get(self, key):
        if self.should_fail:
            raise Exception("Redis read failed")
        return self.db.get(key)

    async def exists(self, key):
        if self.should_fail:
            raise Exception("Redis exists failed")
        return key in self.db

@pytest.mark.asyncio
async def test_live_computation_fallback_when_snapshot_missing(async_client: AsyncClient, db_session: AsyncSession, create_test_user):
    # Clear DB tables for clean test
    await db_session.execute(Complaint.__table__.delete())
    await db_session.execute(AnalyticsSnapshot.__table__.delete())
    await db_session.commit()

    officer = await create_test_user(
        email="officer_cm@example.com",
        role=RoleEnum.OFFICER,
        name="Officer Vikram"
    )
    
    c1 = Complaint(
        ticket_id="DL-2026-CM1",
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
    db_session.add(c1)
    await db_session.commit()
    
    # Clear in-memory cache
    _in_memory_cache["data"] = None
    _in_memory_cache["expires_at"] = 0.0
    
    mock_redis = MockRedis(should_fail=False)
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        response = await async_client.get("/api/v1/analytics")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure & live computed values
        assert "metrics" in data
        assert data["metrics"]["total_complaints"] == 1
        assert data["metrics"]["resolved"] == 1
        assert data["metrics"]["average_resolution_time"] == 10.0
        assert data["district_distribution"]["South Delhi"] == 1
        assert data["heatmap"]["South Delhi"] == 1
        assert data["sla_metrics"]["MCD"] == 10.0
        assert len(data["officer_ranking"]) == 1
        assert data["officer_ranking"][0]["officer_name"] == "Officer Vikram"

@pytest.mark.asyncio
async def test_cache_hit_returns_immediately(async_client: AsyncClient):
    # Clear in-memory cache
    _in_memory_cache["data"] = None
    _in_memory_cache["expires_at"] = 0.0

    cached_payload = {
        "metrics": {
            "total_complaints": 99,
            "pending": 9,
            "resolved": 90,
            "escalated": 1,
            "average_resolution_time": 5.0,
            "average_sla": 48.0
        },
        "district_distribution": {"New Delhi": 99},
        "category_distribution": {"SANITATION": 99},
        "heatmap": {"New Delhi": 99},
        "sla_metrics": {"MCD": 5.0},
        "officer_ranking": []
    }
    
    mock_redis = MockRedis(should_fail=False)
    await mock_redis.set("cm_dashboard_analytics_cache", json.dumps(cached_payload))
    
    # Patch compute_snapshot and get_snapshot to throw exceptions if called,
    # ensuring they are never executed on a cache hit.
    with patch("redis.asyncio.from_url", return_value=mock_redis), \
         patch("app.services.analytics.AnalyticsSnapshotService.get_snapshot", side_effect=Exception("Should not call get_snapshot")), \
         patch("app.services.analytics.AnalyticsSnapshotService.compute_snapshot", side_effect=Exception("Should not call compute_snapshot")):
             
        response = await async_client.get("/api/v1/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["total_complaints"] == 99
        assert data["district_distribution"]["New Delhi"] == 99

@pytest.mark.asyncio
async def test_cache_ttl_expiration(async_client: AsyncClient, db_session: AsyncSession):
    # Clear snapshot table
    await db_session.execute(AnalyticsSnapshot.__table__.delete())
    await db_session.commit()

    # Pre-populate in-memory cache with expired data
    _in_memory_cache["data"] = {
        "metrics": {"total_complaints": 10, "pending": 5, "resolved": 5, "escalated": 0, "average_resolution_time": 0.0, "average_sla": 0.0},
        "district_distribution": {},
        "category_distribution": {},
        "heatmap": {},
        "sla_metrics": {},
        "officer_ranking": []
    }
    _in_memory_cache["expires_at"] = time.time() - 10.0 # Expired 10s ago
    
    mock_redis = MockRedis(should_fail=False)
    
    updated_snapshot = {
        "timestamp": "2026-06-20T22:00:00Z",
        "total_complaints": 200,
        "pending": 50,
        "resolved": 150,
        "escalated": 5,
        "average_sla": 100.0,
        "average_resolution_time": 6.0,
        "top_departments": {},
        "top_districts": {"Central": 200},
        "top_categories": {},
        "officer_ranking": [],
        "department_sla_hours": {}
    }
    
    # Save snapshot record in database so the database query finds it
    record = AnalyticsSnapshot(key="analytics_snapshot", data=updated_snapshot)
    db_session.add(record)
    await db_session.commit()
    
    with patch("redis.asyncio.from_url", return_value=mock_redis), \
         patch("app.services.analytics.AnalyticsSnapshotService.get_snapshot", return_value=updated_snapshot):
        
        response = await async_client.get("/api/v1/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["total_complaints"] == 200
        assert data["district_distribution"]["Central"] == 200

@pytest.mark.asyncio
async def test_redis_downtime_falls_back_to_in_memory(async_client: AsyncClient):
    # Setup valid in-memory cache
    _in_memory_cache["data"] = {
        "metrics": {"total_complaints": 55, "pending": 5, "resolved": 50, "escalated": 0, "average_resolution_time": 0.0, "average_sla": 0.0},
        "district_distribution": {"East Delhi": 55},
        "category_distribution": {},
        "heatmap": {},
        "sla_metrics": {},
        "officer_ranking": []
    }
    _in_memory_cache["expires_at"] = time.time() + 100.0 # Valid
    
    # Mock Redis to fail on any access
    mock_redis = MockRedis(should_fail=True)
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        response = await async_client.get("/api/v1/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["total_complaints"] == 55
        assert data["district_distribution"]["East Delhi"] == 55
