import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.complaint import Complaint
from app.models.complaint_update import ComplaintUpdate

logger = logging.getLogger("cm_dashboard.services.complaint_tracking")

class ComplaintTrackingService:
    @staticmethod
    async def get_tracking_data(ticket_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Fetch complaint tracking data by ticket_id.
        Includes attachments and chronological status updates.
        Returns None if not found or soft-deleted.
        """
        try:
            # 1. Fetch complaint with preloaded attachments, updates, and officer details
            stmt = (
                select(Complaint)
                .where(Complaint.ticket_id == ticket_id)
                .options(
                    selectinload(Complaint.attachments),
                    selectinload(Complaint.updates),
                    selectinload(Complaint.assigned_officer)
                )
            )
            result = await db.execute(stmt)
            complaint = result.scalars().first()

            if not complaint or complaint.is_deleted:
                logger.info(f"Complaint tracking failed: ticket_id {ticket_id} not found or deleted.")
                return None

            # 2. Sort updates ascending by created_at
            # secondary sort by ID to guarantee deterministic order
            sorted_updates = sorted(
                complaint.updates,
                key=lambda u: (u.created_at, u.id)
            )

            # 3. Construct timeline
            timeline = []
            for update in sorted_updates:
                timeline.append({
                    "status": update.status,
                    "note": update.note,
                    "created_at": update.created_at
                })

            # If there are no update records, construct a default 'SUBMITTED' event
            if not timeline:
                timeline.append({
                    "status": "SUBMITTED",
                    "note": "Complaint submitted.",
                    "created_at": complaint.created_at
                })

            # 4. Construct attachments list
            attachments = []
            for attach in complaint.attachments:
                attachments.append({
                    "file_url": attach.file_url,
                    "created_at": attach.created_at
                })

            # 5. Build response dictionary
            return {
                "ticket_id": complaint.ticket_id,
                "status": complaint.status,
                "priority": complaint.priority,
                "category": complaint.category,
                "department": complaint.department,
                "district": complaint.district,
                "title": complaint.title,
                "description": complaint.description,
                "assigned_officer": complaint.assigned_officer.name if complaint.assigned_officer else None,
                "assigned_to": complaint.assigned_to,
                "created_at": complaint.created_at,
                "updated_at": complaint.updated_at,
                "attachments": attachments,
                "timeline": timeline
            }

        except Exception as e:
            logger.error(f"Error fetching tracking data for ticket {ticket_id}: {e}", exc_info=True)
            raise e
