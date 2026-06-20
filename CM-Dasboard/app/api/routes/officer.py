from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.api.deps import CurrentUser, get_db, require_role, Officer
from app.models.complaint import Complaint, ComplaintStatus
from app.models.complaint_update import ComplaintUpdate
from app.services.storage.attachment import AttachmentService
from app.schemas.complaint import Complaint as ComplaintSchema

router = APIRouter()

@router.get("/complaints", response_model=List[ComplaintSchema])
async def get_assigned_complaints(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(Officer))
):
    query = select(Complaint).filter(Complaint.assigned_to == current_user.id)
    result = await db.execute(query)
    return result.scalars().all()

@router.put("/complaints/{ticket_id}/status")
async def update_complaint_status(
    ticket_id: str,
    status_update: str = Form(...),
    note: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(Officer))
):
    try:
        new_status = ComplaintStatus(status_update.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    query = select(Complaint).filter(
        Complaint.ticket_id == ticket_id,
        Complaint.assigned_to == current_user.id
    )
    result = await db.execute(query)
    complaint = result.scalars().first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found or not assigned to you")

    complaint.status = new_status

    db_update = ComplaintUpdate(
        complaint_id=complaint.id,
        status=new_status.value,
        note=note or "Status updated by officer.",
        updated_by=current_user.id
    )
    db.add(db_update)
    await db.commit()

    return {"msg": "Status updated successfully", "status": new_status.value}

@router.post("/complaints/{ticket_id}/proof")
async def upload_proof(
    ticket_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(Officer))
):
    query = select(Complaint).filter(
        Complaint.ticket_id == ticket_id,
        Complaint.assigned_to == current_user.id
    )
    result = await db.execute(query)
    complaint = result.scalars().first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found or not assigned to you")

    attach_rec = await AttachmentService.validate_and_upload(
        file=file,
        complaint_id=complaint.id,
        db=db
    )
    await db.commit()

    return {"msg": "Proof uploaded successfully", "file_url": attach_rec.file_url}
