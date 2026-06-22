import os
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import deps
from app.db.session import get_db
from app.models.complaint import Complaint, PriorityEnum, ComplaintStatus
from app.models.complaint_update import ComplaintUpdate
from app.models.attachment import Attachment
from app.schemas.complaint import ComplaintSubmissionResponse, CrisisCreate, CrisisUpdate, ComplaintTrackingResponse
from app.services.ml.inference import MLInferenceService
from app.services.email.smtp import async_send_complaint_acknowledgement_email
from app.services.storage.attachment import AttachmentService
from app.engines.routing import RoutingEngine
from app.services.notification.service import NotificationService
from app.services.complaint_tracking import ComplaintTrackingService

logger = logging.getLogger(__name__)
router = APIRouter()

# Validation regex patterns
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
PHONE_REGEX = r"^\+?[0-9]{10,15}$"
TICKET_REGEX = r"^DL-\d{4}-[A-Z0-9]{6}$"

def get_sla_for_priority(priority: PriorityEnum) -> str:
    if priority == PriorityEnum.CRITICAL:
        return "24 Hours"
    elif priority == PriorityEnum.HIGH:
        return "3 Days"
    elif priority == PriorityEnum.MEDIUM:
        return "5 Days"
    else:
        return "7 Days"

def get_department_for_category(category: str) -> str:
    cat = category.strip().upper()
    if not cat or cat == "OTHER":
        return "GENERAL_DEPT"
    if cat.endswith("_DEPT"):
        return cat
    return f"{cat}_DEPT"

@router.post("/", response_model=ComplaintSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_complaint(
    background_tasks: BackgroundTasks,
    citizen_name: str = Form(...),
    citizen_email: str = Form(...),
    citizen_phone: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    district: str = Form(...),
    category: Optional[str] = Form(None),
    attachments: List[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db)
):
    # 1. Input Validations
    citizen_email = citizen_email.lower().strip()
    citizen_phone = citizen_phone.strip()
    citizen_name = citizen_name.strip()
    title = title.strip()
    description = description.strip()
    district = district.strip()

    if not citizen_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Citizen name cannot be empty.")
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Complaint title cannot be empty.")
    if not description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Complaint description cannot be empty.")
    if not district:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="District cannot be empty.")

    if not re.match(EMAIL_REGEX, citizen_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format."
        )

    if not re.match(PHONE_REGEX, citizen_phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format. Expected 10-15 digits optionally starting with '+'."
        )

    if len(attachments) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many files. Maximum 5 attachments allowed."
        )

    # 2. Duplicate submission prevention within 5 minutes
    duplicate_query = select(Complaint).filter(
        Complaint.citizen_email == citizen_email,
        Complaint.title == title,
        Complaint.description == description,
        Complaint.created_at >= datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    dup_res = await db.execute(duplicate_query)
    if dup_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate complaint submitted. Please wait 5 minutes before submitting again."
        )

    # 3. Auto-Classification Fallback
    ml_service = MLInferenceService()
    final_category = category
    confidence_score = 1.0
    
    if not final_category or not final_category.strip():
        # Classify using fine-tuned model
        ml_res = ml_service.predict(description)

        predicted_labels = ml_res.get(
    "category_pred",
    ["OTHER"]
)
        predicted_labels = ml_res.get("category_pred", ["OTHER"])
        final_category = predicted_labels[0] if predicted_labels else "OTHER"
        confidence_score = ml_res.get("confidence_score", 0.5)
    
    final_category = final_category.strip()

    # Determine severity/priority
    pred_priority_str = ml_service.predict_severity(description)
    final_priority = PriorityEnum[pred_priority_str]

    # Map department
    final_department = get_department_for_category(final_category)

    # 3.5. Route Complaint (Dynamically calculated threshold using Policy Engine)
    try:
        from app.services.rl.policy import DynamicPolicyEngine
        policy_engine = DynamicPolicyEngine()
        policy = policy_engine.get_current_policy()
        confidence_threshold = policy.get("confidence_storage_threshold", 0.75)
    except Exception as e:
        logger.warning(f"Failed to fetch dynamic policy: {e}. Using baseline 0.75")
        confidence_threshold = 0.75

    assigned_to = None
    if confidence_score >= confidence_threshold:
        assigned_to = await RoutingEngine.route_complaint(final_category, district, db)

    # 4. Generate Ticket ID (using UUID for distributed safety)
    current_year = datetime.now().year
    ticket_id = f"DL-{current_year}-{uuid.uuid4().hex[:6].upper()}"

    initial_status = ComplaintStatus.ASSIGNED if assigned_to is not None else ComplaintStatus.SUBMITTED

    # 5. Database Save & File Storage Transaction
    db_complaint = Complaint(
        ticket_id=ticket_id,
        citizen_name=citizen_name,
        citizen_email=citizen_email,
        citizen_phone=citizen_phone,
        title=title,
        description=description,
        category=final_category,
        department=final_department,
        district=district,
        priority=final_priority,
        status=initial_status,
        assigned_to=assigned_to
    )

    uploaded_attachments = []
    try:
        db.add(db_complaint)
        await db.flush() # Populate ID

        for file in attachments:
            if not file.filename:
                continue
            attach_rec = await AttachmentService.validate_and_upload(
                file=file,
                complaint_id=db_complaint.id,
                db=db
            )
            uploaded_attachments.append(attach_rec)

        db_update = ComplaintUpdate(
            complaint_id=db_complaint.id,
            status=initial_status.value,
            note="Complaint automatically routed." if assigned_to else "Complaint submitted.",
            updated_by=None
        )
        db.add(db_update)

        await db.commit()
        try:
         from app.services.memory.complaint_ingestor import (
        ingest_complaint
    )

         background_tasks.add_task(
        ingest_complaint,
        complaint_text=description,
        category=final_category,
        department=final_department,
        status=initial_status.value
    )

        except Exception as ingest_err:
         logger.error(
        f"FAISS ingestion failed for {ticket_id}: {ingest_err}",
        exc_info=True
    )
    except Exception as e:
        # Rollback DB transaction
        await db.rollback()
        # Clean up files uploaded during this request
        for attach in uploaded_attachments:
            file_url = attach.file_url
            if file_url.startswith("/static/uploads/"):
                local_path = os.path.join("app", file_url.lstrip("/"))
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except Exception as cleanup_err:
                    logger.error(f"Failed to delete local fallback file {local_path} during rollback: {cleanup_err}")
            elif settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY and settings.S3_BUCKET:
                try:
                    key = file_url.split("/")[-1]
                    await asyncio.to_thread(AttachmentService._delete_s3_keys, [key])
                except Exception as s3_cleanup_err:
                    logger.error(f"Failed to delete S3 object {file_url} during rollback: {s3_cleanup_err}")
        
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Failed to store complaint registration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register complaint due to storage or database error."
        )

    # 6. Async Acknowledgement Email (Failure should not rollback complaint)
    estimated_sla = get_sla_for_priority(final_priority)
    try:
        await async_send_complaint_acknowledgement_email(
            email_to=citizen_email,
            citizen_name=citizen_name,
            ticket_id=ticket_id,
            status=initial_status.value,
            estimated_sla=estimated_sla
        )
    except Exception as email_err:
        logger.error(f"Non-blocking email delivery failure for ticket {ticket_id}: {email_err}")

    # 6.5 Async App Notification for Assignment
    if assigned_to is not None:
        NotificationService.dispatch_assigned_notification(
            user_id=assigned_to,
            ticket_id=ticket_id,
            background_tasks=background_tasks
        )

    # 6. Trigger APScheduler Pipeline Natively
    try:
        from app.tasks.pipeline import execute_core
        from app.main import scheduler
        
        # Dispatch asynchronously via APScheduler instead of Celery for native fallback
        scheduler.add_job(execute_core, args=[ticket_id])
        logger.info(f"Scheduled APScheduler pipeline task for complaint {ticket_id}")
    except Exception as e:
        logger.error(f"Failed to trigger APScheduler pipeline for {ticket_id}: {e}", exc_info=True)
        
    # 7. Socket.io Event (Notify Admins)
    try:
        from app.api.socket import sio
        await sio.emit("newComplaint", {
            "ticket_id": ticket_id,
            "status": initial_status.value,
            "category": final_category,
            "priority": final_priority.value
        }, room="admins")
    except Exception as e:
        logger.error(f"Failed to emit newComplaint via socket: {e}")

    return ComplaintSubmissionResponse(
        ticket_id=ticket_id,
        status=initial_status.value,
        estimated_sla=estimated_sla
    )


@router.get("/track/{ticket_id}", response_model=ComplaintTrackingResponse)
async def track_complaint(
    ticket_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for citizens to track the status and timeline of a complaint by its ticket_id.
    Does not require authentication.
    """
    # 1. Validate ticket format
    if not re.match(TICKET_REGEX, ticket_id, re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticket format. Expected format: DL-YYYY-XXXXXX"
        )

    # 2. Fetch tracking details
    tracking_data = await ComplaintTrackingService.get_tracking_data(ticket_id, db)
    if not tracking_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with ticket ID '{ticket_id}' not found."
        )

    return tracking_data

@router.get("/my-complaints", response_model=List[ComplaintTrackingResponse])
async def get_my_complaints(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(deps.require_role(deps.Citizen))
):
    """
    Endpoint for citizens to fetch all their submitted complaints.
    """
    # In a real app, you might use current_user.email to filter or link citizen_email.
    # We will assume current_user.email matches the citizen_email.
    from sqlalchemy.orm import selectinload
    query = (
        select(Complaint)
        .filter(Complaint.citizen_email == current_user.email)
        .options(selectinload(Complaint.assigned_officer))
        .order_by(Complaint.created_at.desc())
    )
    result = await db.execute(query)
    complaints = result.scalars().all()
    
    # Transform to TrackingResponse format or similar for the frontend
    tracking_data_list = []
    for c in complaints:
        tracking_data_list.append({
            "ticket_id": c.ticket_id,
            "status": c.status,
            "category": c.category,
            "department": c.department,
            "priority": c.priority,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "title": c.title,
            "description": c.description,
            "assigned_officer": c.assigned_officer.name if c.assigned_officer else None,
            "assigned_to": c.assigned_to,
            "district": c.district,
            "attachments": [],
            "timeline": []
        })
        
    return tracking_data_list
