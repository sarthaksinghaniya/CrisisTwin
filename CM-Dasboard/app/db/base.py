# Import Base class and all models here
# This allows Alembic to easily auto-detect all models for migrations by importing app.db.base.Base

from app.models.base import Base  # noqa
from app.models.user import User  # noqa
from app.models.incident import Incident  # noqa
from app.models.report import Report  # noqa
from app.models.agent import Agent  # noqa
from app.models.assignment import Assignment  # noqa
