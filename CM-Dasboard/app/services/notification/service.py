import logging
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import BackgroundTasks
from sqlalchemy.future import select
from sqlalchemy import func

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.notification import Notification
from app.services.email.smtp import async_send_notification_email

logger = logging.getLogger(__name__)

async def notification_background_job(user_id: uuid.UUID, message: str, subject: str) -> None:
    """
    Background job executed via BackgroundTasks.
    Validates user active status, checks for duplicate/storm alerts,
    saves the database notification, and dispatches SMTP emails.
    """
    logger.info(f"Starting background notification job for user {user_id}")
    
    async with AsyncSessionLocal() as db:
        # 1. Edge Case: Verify user exists and is active
        res_user = await db.execute(select(User).filter(User.id == user_id, User.is_deleted == False))
        user = res_user.scalars().first()
        if not user:
            logger.warning(f"Notification suppressed: User ID {user_id} does not exist or has been deleted.")
            return

        now = datetime.now(timezone.utc)
        one_minute_ago = now - timedelta(minutes=1)

        # 2. Edge Case: Duplicate notification detection (within 1 minute)
        dup_query = select(Notification).filter(
            Notification.user_id == user_id,
            Notification.message == message,
            Notification.created_at >= one_minute_ago
        )
        res_dup = await db.execute(dup_query)
        if res_dup.scalars().first():
            logger.info(f"Duplicate notification suppressed for user {user_id}: '{message[:30]}...'")
            return

        # 3. Edge Case: Notification storm suppression (max 10 within 1 minute)
        storm_query = select(func.count(Notification.id)).filter(
            Notification.user_id == user_id,
            Notification.created_at >= one_minute_ago
        )
        res_storm = await db.execute(storm_query)
        recent_count = res_storm.scalar() or 0
        
        send_email = True
        if recent_count >= 10:
            logger.warning(
                f"Notification storm detected for user {user_id} ({recent_count} recent alerts). "
                f"Suppressing email delivery. Dashboard alert will still be registered."
            )
            send_email = False

        # 4. Save Notification DB entry (Dashboard channel)
        db_notification = Notification(
            user_id=user_id,
            message=message,
            is_read=False,
            created_at=now
        )
        
        try:
            db.add(db_notification)
            await db.commit()
            logger.info(f"Successfully registered dashboard notification for user {user_id}")
        except Exception as db_err:
            await db.rollback()
            logger.error(f"Failed to save notification record for user {user_id}: {db_err}", exc_info=True)
            return

        # 5. Send Email Alert (Email channel)
        if send_email and user.email:
            try:
                await async_send_notification_email(
                    email_to=user.email,
                    subject=subject,
                    message=message
                )
                logger.info(f"Successfully sent notification email to {user.email}")
            except Exception as email_err:
                # Catch SMTP errors gracefully (do not raise exception or rollback database)
                logger.error(
                    f"Non-blocking email delivery failure for user {user.email} (SMTP down/unavailable): {email_err}"
                )

class NotificationService:
    """
    Service triggers mapping specific complaint events to background notification tasks.
    """

    @staticmethod
    def dispatch_assigned_notification(
        user_id: uuid.UUID,
        ticket_id: str,
        background_tasks: BackgroundTasks
    ) -> None:
        message = f"Complaint ticket {ticket_id} has been assigned to you."
        subject = f"Grievance Assignment - Ticket {ticket_id}"
        background_tasks.add_task(notification_background_job, user_id, message, subject)

    @staticmethod
    def dispatch_status_changed_notification(
        user_id: uuid.UUID,
        ticket_id: str,
        new_status: str,
        background_tasks: BackgroundTasks
    ) -> None:
        message = f"The status of complaint ticket {ticket_id} has changed to {new_status}."
        subject = f"Grievance Status Update - Ticket {ticket_id}"
        background_tasks.add_task(notification_background_job, user_id, message, subject)

    @staticmethod
    def dispatch_escalation_notification(
        user_id: uuid.UUID,
        ticket_id: str,
        background_tasks: BackgroundTasks
    ) -> None:
        message = f"Complaint ticket {ticket_id} has been escalated to you due to resolution delay."
        subject = f"Urgent Grievance Escalation - Ticket {ticket_id}"
        background_tasks.add_task(notification_background_job, user_id, message, subject)

    @staticmethod
    def dispatch_resolved_notification(
        user_id: uuid.UUID,
        ticket_id: str,
        background_tasks: BackgroundTasks
    ) -> None:
        message = f"Complaint ticket {ticket_id} has been marked as RESOLVED."
        subject = f"Grievance Resolved - Ticket {ticket_id}"
        background_tasks.add_task(notification_background_job, user_id, message, subject)
