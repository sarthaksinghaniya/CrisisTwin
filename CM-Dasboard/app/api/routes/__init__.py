from fastapi import APIRouter

from .users import router as users_router
from .incidents import router as incidents_router
from .reports import router as reports_router
from .agents import router as agents_router
from .assignments import router as assignments_router

api_router = APIRouter()

api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(assignments_router, prefix="/assignments", tags=["assignments"])
