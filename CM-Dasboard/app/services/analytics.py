import logging
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import redis.asyncio as aioredis

from app.core.config import settings
from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.user import User
from app.models.analytics_snapshot import AnalyticsSnapshot

logger = logging.getLogger("cm_dashboard.services.analytics")

class AnalyticsSnapshotService:
    # Priority to SLA hours mapping
    SLA_HOURS = {
        PriorityEnum.CRITICAL: 24,
        PriorityEnum.HIGH: 48,
        PriorityEnum.MEDIUM: 168,   # 7 days
        PriorityEnum.LOW: 336,      # 14 days
    }

    @classmethod
    async def compute_snapshot(cls, session: AsyncSession) -> dict:
        """
        Executes queries to calculate current analytics snapshot stats.
        Handles edge cases:
          - No complaints -> average_sla & average_resolution_time = 0.0
          - Missing district -> grouped under "Unknown"
          - Negative duration -> clamped to 0.0
        """
        logger.info("Computing analytics snapshot...")
        
        # Fetch all active complaints
        stmt = select(Complaint).filter(Complaint.is_deleted == False)
        res = await session.execute(stmt)
        complaints = res.scalars().all()
        
        total_complaints = len(complaints)
        
        # 1. Status counts
        pending_count = 0
        resolved_count = 0
        escalated_count = 0
        
        # 2. SLA calculations
        total_sla_hours = 0.0
        
        # 3. Resolution time calculations
        total_resolution_hours = 0.0
        resolved_complaints_count = 0
        
        # 4. Aggregation maps
        dept_counts = {}
        district_counts = {}
        category_counts = {}
        
        for c in complaints:
            # Pending statuses: SUBMITTED, PROCESSING, ASSIGNED, ESCALATED
            if c.status in (ComplaintStatus.SUBMITTED, ComplaintStatus.PROCESSING, ComplaintStatus.ASSIGNED, ComplaintStatus.ESCALATED):
                pending_count += 1
            if c.status == ComplaintStatus.RESOLVED:
                resolved_count += 1
            if c.status == ComplaintStatus.ESCALATED:
                escalated_count += 1
                
            # SLA calculations (average of SLA limit in hours for all complaints)
            priority = c.priority or PriorityEnum.MEDIUM
            total_sla_hours += cls.SLA_HOURS.get(priority, 168)
            
            # Resolution time
            if c.status == ComplaintStatus.RESOLVED:
                resolved_complaints_count += 1
                # Resolution time in hours
                res_time = (c.updated_at - c.created_at).total_seconds() / 3600.0
                # Edge Case: Negative duration -> clamp to 0.0
                if res_time < 0:
                    res_time = 0.0
                total_resolution_hours += res_time
                
            # Group top departments
            dept = c.department or "Unknown"
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
            
            # Group top districts (Edge Case: Missing district -> map to "Unknown")
            district = c.district or "Unknown"
            if not district.strip():
                district = "Unknown"
            district_counts[district] = district_counts.get(district, 0) + 1
            
            # Group top categories
            cat = c.category or "Unknown"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            
        average_sla = total_sla_hours / total_complaints if total_complaints > 0 else 0.0
        average_resolution_time = total_resolution_hours / resolved_complaints_count if resolved_complaints_count > 0 else 0.0
        
        # Sort aggregations descending
        top_departments = dict(sorted(dept_counts.items(), key=lambda x: x[1], reverse=True))
        top_districts = dict(sorted(district_counts.items(), key=lambda x: x[1], reverse=True))
        top_categories = dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True))
        
        # 5. Officer ranking: officers by count of resolved complaints assigned to them
        officer_resolved_counts = {}
        for c in complaints:
            if c.status == ComplaintStatus.RESOLVED and c.assigned_to:
                officer_resolved_counts[c.assigned_to] = officer_resolved_counts.get(c.assigned_to, 0) + 1
                
        officer_ranking = []
        if officer_resolved_counts:
            # Fetch User objects for these IDs
            officer_ids = list(officer_resolved_counts.keys())
            user_stmt = select(User).filter(User.id.in_(officer_ids))
            user_res = await session.execute(user_stmt)
            users_map = {u.id: u.name for u in user_res.scalars().all()}
            
            for o_id, count in officer_resolved_counts.items():
                officer_ranking.append({
                    "officer_id": str(o_id),
                    "officer_name": users_map.get(o_id, "Unknown Officer"),
                    "resolved_count": count
                })
            # Sort by resolved_count descending
            officer_ranking.sort(key=lambda x: x["resolved_count"], reverse=True)
            
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_complaints": total_complaints,
            "pending": pending_count,
            "resolved": resolved_count,
            "escalated": escalated_count,
            "average_sla": round(average_sla, 2),
            "average_resolution_time": round(average_resolution_time, 2),
            "top_departments": top_departments,
            "top_districts": top_districts,
            "top_categories": top_categories,
            "officer_ranking": officer_ranking
        }

    @classmethod
    async def save_snapshot(cls, snapshot: dict, session: AsyncSession) -> None:
        """
        Saves the computed snapshot. Tries Redis first, falls back to Postgres.
        """
        redis_saved = False
        
        # Try Redis storage
        try:
            r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
            async with r:
                await r.set("analytics_snapshot", json.dumps(snapshot))
            logger.info("Successfully saved analytics snapshot to Redis.")
            redis_saved = True
        except Exception as e:
            logger.warning(f"Failed to save analytics snapshot to Redis: {e}. Falling back to PostgreSQL.")
            
        # Postgres fallback
        try:
            # Check if a snapshot record already exists
            stmt = select(AnalyticsSnapshot).filter(AnalyticsSnapshot.key == "analytics_snapshot")
            res = await session.execute(stmt)
            db_record = res.scalars().first()
            
            if db_record:
                db_record.data = snapshot
                db_record.updated_at = datetime.now(timezone.utc)
            else:
                db_record = AnalyticsSnapshot(
                    key="analytics_snapshot",
                    data=snapshot
                )
                session.add(db_record)
            await session.commit()
            logger.info("Successfully saved analytics snapshot to PostgreSQL.")
        except Exception as e:
            logger.error(f"Failed to save analytics snapshot to PostgreSQL: {e}")
            await session.rollback()
            raise e

    @classmethod
    async def get_snapshot(cls, session: AsyncSession) -> dict:
        """
        Retrieves the latest analytics snapshot.
        Checks Redis first, falls back to PostgreSQL.
        """
        # Try Redis first
        try:
            r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
            async with r:
                val = await r.get("analytics_snapshot")
                if val:
                    logger.info("Retrieved analytics snapshot from Redis.")
                    return json.loads(val)
        except Exception as e:
            logger.warning(f"Failed to read analytics snapshot from Redis: {e}. Checking PostgreSQL.")
            
        # Fallback to Postgres
        try:
            stmt = select(AnalyticsSnapshot).filter(AnalyticsSnapshot.key == "analytics_snapshot")
            res = await session.execute(stmt)
            db_record = res.scalars().first()
            if db_record:
                logger.info("Retrieved analytics snapshot from PostgreSQL.")
                return db_record.data
        except Exception as e:
            logger.error(f"Failed to read analytics snapshot from PostgreSQL: {e}")
            
        # Return safe defaults if all fail
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_complaints": 0,
            "pending": 0,
            "resolved": 0,
            "escalated": 0,
            "average_sla": 0.0,
            "average_resolution_time": 0.0,
            "top_departments": {},
            "top_districts": {},
            "top_categories": {},
            "officer_ranking": []
        }
