from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel

from app.api.deps import get_db, require_role, Admin
from app.models.complaint import Complaint, ComplaintStatus
from app.models.complaint_update import ComplaintUpdate
from app.services.storage.attachment import AttachmentService
from app.schemas.complaint import Complaint as ComplaintSchema
from app.models.user import User
from app.services.notification.service import NotificationService

router = APIRouter()

class StatusUpdateRequest(BaseModel):
    status: str
    note: str = None
    assigned_to: str = None

@router.get("/complaints", response_model=List[ComplaintSchema])
async def get_all_complaints(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Admin))
):
    # Admins can see all complaints
    query = select(Complaint).order_by(Complaint.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.patch("/complaints/{ticket_id}")
async def update_complaint_status(
    ticket_id: str,
    payload: StatusUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Admin))
):
    status_str = payload.status.upper()
    if status_str == "IN_PROGRESS":
        status_str = "PROCESSING"
    elif status_str == "REJECTED":
        status_str = "CLOSED"

    try:
        new_status = ComplaintStatus(status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    query = select(Complaint).filter(Complaint.ticket_id == ticket_id)
    result = await db.execute(query)
    complaint = result.scalars().first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    old_status = complaint.status
    old_assigned_to = complaint.assigned_to

    complaint.status = new_status

    assigned_changed = False
    if payload.assigned_to is not None:
        if payload.assigned_to == "":
            new_assigned_to = None
        else:
            try:
                import uuid
                new_assigned_to = uuid.UUID(payload.assigned_to)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid assigned_to UUID")
        
        if old_assigned_to != new_assigned_to:
            complaint.assigned_to = new_assigned_to
            assigned_changed = True

    db_update = ComplaintUpdate(
        complaint_id=complaint.id,
        status=new_status.value,
        note=payload.note or "Status updated by admin.",
        updated_by=current_user.id
    )
    db.add(db_update)
    await db.commit()

    try:
        query_user = select(User).filter(User.email == complaint.citizen_email)
        user_res = await db.execute(query_user)
        citizen_user = user_res.scalars().first()
        
        if citizen_user:
            from app.api.socket import sio
            await sio.emit("statusUpdated", {
                "ticket_id": ticket_id,
                "status": new_status.value
            }, room=str(citizen_user.id))
            
            # Dispatch citizen notification on status change
            if new_status != old_status:
                if new_status == ComplaintStatus.RESOLVED:
                    NotificationService.dispatch_resolved_notification(
                        user_id=citizen_user.id,
                        ticket_id=ticket_id,
                        background_tasks=background_tasks
                    )
                else:
                    NotificationService.dispatch_status_changed_notification(
                        user_id=citizen_user.id,
                        ticket_id=ticket_id,
                        new_status=new_status.value,
                        background_tasks=background_tasks
                    )
    except Exception as e:
        print(f"Failed to emit statusUpdated or dispatch status notifications: {e}")

    # Dispatch assignment notification to the assigned officer
    if assigned_changed and complaint.assigned_to is not None:
        try:
            NotificationService.dispatch_assigned_notification(
                user_id=complaint.assigned_to,
                ticket_id=ticket_id,
                background_tasks=background_tasks
            )
        except Exception as e:
            print(f"Failed to dispatch assignment notification: {e}")

    return {"msg": "Status updated successfully", "status": new_status.value}

@router.post("/complaints/{ticket_id}/proof")
async def upload_proof(
    ticket_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Admin))
):
    query = select(Complaint).filter(Complaint.ticket_id == ticket_id)
    result = await db.execute(query)
    complaint = result.scalars().first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    attach_rec = await AttachmentService.validate_and_upload(
        file=file,
        complaint_id=complaint.id,
        db=db
    )
    await db.commit()

    return {"msg": "Proof uploaded successfully", "file_url": attach_rec.file_url}
