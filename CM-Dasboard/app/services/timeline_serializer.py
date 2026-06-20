import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import RoleEnum
from app.models.complaint_update import ComplaintUpdate

logger = logging.getLogger("cm_dashboard.services.timeline_serializer")

# Status-to-color mapping
STATUS_COLOR_MAP = {
    "SUBMITTED": "grey",
    "OPEN": "grey",
    "CLOSED": "grey",
    "ASSIGNED": "yellow",
    "PROCESSING": "yellow",
    "IN_PROGRESS": "yellow",
    "ESCALATED": "red",
    "RESOLVED": "green",
    "FAILED": "red",
    "FAILED_FINAL": "red"
}

def get_relative_time(dt: datetime) -> str:
    """
    Format a datetime as a human-readable relative time string.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago" if minutes > 1 else "1m ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago" if hours > 1 else "1h ago"

    days = hours // 24
    if days < 30:
        return f"{days}d ago" if days > 1 else "1d ago"

    months = days // 30
    if months < 12:
        return f"{months}mo ago" if months > 1 else "1mo ago"

    years = months // 12
    return f"{years}y ago" if years > 1 else "1y ago"

class TimelineSerializationService:
    @staticmethod
    def serialize_timeline(complaint: Complaint) -> Dict[str, Any]:
        """
        Serialize a Complaint and its history updates into a chronological timeline payload.
        Handles relative time, color metadata, matching proof URLs, comment count, and feedback.
        """
        # Retrieve relationship lists safely from __dict__ to avoid triggering lazy load MissingGreenlet exceptions
        comments = complaint.__dict__.get("comments") or []
        feedbacks = complaint.__dict__.get("feedbacks") or []
        attachments = complaint.__dict__.get("attachments") or []
        updates = complaint.__dict__.get("updates") or []

        # Remove any SQLAlchemy internal state indicators (like LoaderCallable or NO_VALUE)
        from sqlalchemy.orm.attributes import NO_VALUE
        if comments is NO_VALUE: comments = []
        if feedbacks is NO_VALUE: feedbacks = []
        if attachments is NO_VALUE: attachments = []
        if updates is NO_VALUE: updates = []

        ticket_id = complaint.ticket_id
        current_status = complaint.status.value if hasattr(complaint.status, "value") else str(complaint.status)
        comment_count = len(comments)

        # 2. Feedback check
        feedback_submitted = False
        feedback_rating = None
        feedback_remarks = None
        if feedbacks and len(feedbacks) > 0:
            feedback_submitted = True
            # Fetch the most recent feedback
            latest_feedback = sorted(feedbacks, key=lambda f: f.created_at, reverse=True)[0]
            feedback_rating = latest_feedback.rating
            feedback_remarks = latest_feedback.note

        # 3. Sort updates chronologically ascending
        sorted_updates = sorted(updates, key=lambda u: (u.created_at, u.id))

        # 4. Construct timeline events
        timeline_events = []
        
        # Scan all updates and map them to timeline events
        for update in sorted_updates:
            # Resolve updater role name
            updated_by = "System"
            updater = update.__dict__.get("updater")
            if updater and updater is not NO_VALUE:
                role = updater.role
                name = updater.name
                if role == RoleEnum.OFFICER:
                    updated_by = f"Officer ({name})"
                elif role == RoleEnum.HEAD:
                    updated_by = f"Department Head ({name})"
                elif role == RoleEnum.ADMIN:
                    updated_by = f"Admin ({name})"
                elif role == RoleEnum.CITIZEN:
                    updated_by = f"Citizen ({name})"

            # Map color based on status
            status_str = update.status.upper() if update.status else "UNKNOWN"
            color = STATUS_COLOR_MAP.get(status_str, "grey")

            # Associate attachments uploaded within a 15-second threshold window of this update
            proof_urls = []
            if attachments:
                for attach in attachments:
                    time_diff = abs((attach.created_at - update.created_at).total_seconds())
                    if time_diff <= 15:
                        proof_urls.append(attach.file_url)

            # Fallback: if status is RESOLVED and we have any attachments, make sure they are listed if they weren't matched already
            if status_str == "RESOLVED" and not proof_urls and attachments:
                proof_urls = [attach.file_url for attach in attachments]

            timeline_events.append({
                "status": status_str,
                "timestamp": update.created_at,
                "relative_time": get_relative_time(update.created_at),
                "updated_by": updated_by,
                "color": color,
                "proof_urls": proof_urls
            })

        # 5. Handle "No updates" edge case: generate a default submission event
        if not timeline_events:
            color = STATUS_COLOR_MAP.get(current_status, "grey")
            
            # Submission proof (attachments submitted at intake time)
            proof_urls = [attach.file_url for attach in attachments] if attachments else []

            timeline_events.append({
                "status": current_status,
                "timestamp": complaint.created_at,
                "relative_time": get_relative_time(complaint.created_at),
                "updated_by": "System",
                "color": color,
                "proof_urls": proof_urls
            })

        return {
            "ticket_id": ticket_id,
            "current_status": current_status,
            "comment_count": comment_count,
            "feedback_submitted": feedback_submitted,
            "feedback_rating": feedback_rating,
            "feedback_remarks": feedback_remarks,
            "timeline": timeline_events
        }
