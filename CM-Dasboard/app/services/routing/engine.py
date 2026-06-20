import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.user import User, RoleEnum
from app.models.complaint import Complaint, ComplaintStatus

logger = logging.getLogger(__name__)

VALID_DISTRICTS = [
    "North Delhi", "South Delhi", "West Delhi", "East Delhi", 
    "North West Delhi", "North East Delhi", "Central Delhi", 
    "South East Delhi", "South West Delhi", "New Delhi", "Shahdara"
]

CATEGORY_TO_DEPARTMENT = {
    "ROAD": "PWD",
    "ELECTRICITY": "DISCOM",
    "WATER": "DJB",
    "HEALTH": "Health Department",
    "WOMEN SAFETY": "Police",
    "SANITATION": "MCD"
}

class RoutingEngine:
    @staticmethod
    def normalize_district(district: str) -> Optional[str]:
        if not district:
            return None
        cleaned = " ".join(district.strip().split()).lower()
        for valid in VALID_DISTRICTS:
            if valid.lower() == cleaned:
                return valid
        return None

    @staticmethod
    def get_department(category: str) -> str:
        cat = category.strip().upper()
        if not cat or cat == "OTHER":
            return "GENERAL_DEPT"
        
        if cat in CATEGORY_TO_DEPARTMENT:
            return CATEGORY_TO_DEPARTMENT[cat]
            
        if cat.endswith("_DEPT"):
            return cat
        return f"{cat}_DEPT"

    @staticmethod
    async def route_complaint(category: str, district: str, db: AsyncSession) -> Optional[int]:
        """
        Determines the assigned officer based on category, district, and workload.
        Returns the User ID of the assigned officer/head, or None for admin queue.
        """
        target_department = RoutingEngine.get_department(category)
        
        if target_department == "GENERAL_DEPT":
            return None
            
        normalized_district = RoutingEngine.normalize_district(district)
        if not normalized_district:
            return None
            
        # 1. Least Workload Officer Selection
        query = select(User).filter(
            User.role == RoleEnum.OFFICER,
            User.is_deleted == False,
            User.department == target_department,
            User.district == normalized_district
        )
        res = await db.execute(query)
        officers = res.scalars().all()
        
        if officers:
            best_officer_id = None
            min_workload = float('inf')
            
            for officer in officers:
                workload_query = select(func.count(Complaint.id)).filter(
                    Complaint.assigned_to == officer.id,
                    Complaint.status.in_([ComplaintStatus.ASSIGNED, ComplaintStatus.PROCESSING])
                )
                res_wl = await db.execute(workload_query)
                workload = res_wl.scalar() or 0
                
                # Round robin fallback: tie-break with lowest user ID
                if workload < min_workload:
                    min_workload = workload
                    best_officer_id = officer.id
                elif workload == min_workload and best_officer_id is not None:
                    if officer.id < best_officer_id:
                        best_officer_id = officer.id
                        
            if best_officer_id:
                return best_officer_id

        # 2. Department Head Fallback
        query_head = select(User).filter(
            User.role == RoleEnum.HEAD,
            User.is_deleted == False,
            User.department == target_department
        ).order_by(User.id.asc()).limit(1)
        res_head = await db.execute(query_head)
        head = res_head.scalars().first()
        
        if head:
            return head.id
            
        return None
