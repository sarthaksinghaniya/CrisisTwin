# Import Base class and all models here
# This allows Alembic to easily auto-detect all models for migrations by importing app.db.base.Base

from app.models.base import Base  # noqa
from app.models.user import User  # noqa
from app.models.complaint import Complaint  # noqa
from app.models.complaint_update import ComplaintUpdate  # noqa
from app.models.comment import Comment  # noqa
from app.models.attachment import Attachment  # noqa
from app.models.notification import Notification  # noqa
from app.models.otp import OTP  # noqa
from app.models.feedback import Feedback  # noqa
from app.models.escalation import Escalation  # noqa
from app.models.analytics_snapshot import AnalyticsSnapshot  # noqa
