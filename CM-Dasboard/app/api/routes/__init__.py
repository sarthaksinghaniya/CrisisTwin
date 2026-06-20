from fastapi import APIRouter

from .users import router as users_router
from .auth import router as auth_router
from .complaints import router as complaints_router
from .notifications import router as notifications_router
from .officer import router as officer_router
from .escalation import router as escalation_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(complaints_router, prefix="/complaints", tags=["complaints"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(officer_router, prefix="/officer", tags=["officer"])
api_router.include_router(escalation_router, prefix="/escalation", tags=["escalation"])
