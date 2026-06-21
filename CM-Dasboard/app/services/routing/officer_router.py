from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.complaint import Complaint
from app.models.user import RoleEnum


CATEGORY_DEPARTMENT_MAP = {
    "Power": "Power Department",
    "Water": "Delhi Jal Board",
    "Sanitation": "Municipal Corporation",
    "Road": "PWD",
    "Security": "Police",
    "Healthcare": "Health Department",
    "Other": "General Administration"
}


class OfficerRouter:

    @staticmethod
    async def assign_officer(
        db: AsyncSession,
        complaint: Complaint,
    ):

        department = complaint.department
        district = complaint.district

        stmt = (
            select(User)
            .where(
                User.role == RoleEnum.OFFICER,
                User.department == department,
                User.district == district,
                User.is_deleted == False
            )
            .limit(1)
        )

        result = await db.execute(stmt)

        officer = result.scalar_one_or_none()

        if officer:
            return officer

        fallback_stmt = (
            select(User)
            .where(
                User.role == RoleEnum.OFFICER,
                User.department == department,
                User.is_deleted == False
            )
            .limit(1)
        )

        fallback_result = await db.execute(fallback_stmt)

        return fallback_result.scalar_one_or_none()