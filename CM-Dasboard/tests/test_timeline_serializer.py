import pytest
from datetime import datetime, timezone, timedelta

from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.complaint_update import ComplaintUpdate
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.feedback import Feedback
from app.models.user import User, RoleEnum
from app.services.timeline_serializer import TimelineSerializationService, get_relative_time

def test_relative_time_helper():
    now = datetime.now(timezone.utc)
    
    assert get_relative_time(now) == "just now"
    assert get_relative_time(now - timedelta(seconds=15)) == "just now"
    assert get_relative_time(now - timedelta(minutes=1)) == "1m ago"
    assert get_relative_time(now - timedelta(minutes=5)) == "5m ago"
    assert get_relative_time(now - timedelta(hours=1)) == "1h ago"
    assert get_relative_time(now - timedelta(hours=3)) == "3h ago"
    assert get_relative_time(now - timedelta(days=1)) == "1d ago"
    assert get_relative_time(now - timedelta(days=4)) == "4d ago"
    assert get_relative_time(now - timedelta(days=45)) == "1mo ago"
    assert get_relative_time(now - timedelta(days=400)) == "1y ago"

@pytest.mark.asyncio
async def test_serialize_timeline_success(db_session, create_test_user):
    # 1. Setup users
    officer = await create_test_user(
        email="officer_timeline@example.com",
        role=RoleEnum.OFFICER,
        name="Officer Rajesh"
    )
    citizen = await create_test_user(
        email="citizen_timeline@example.com",
        role=RoleEnum.CITIZEN,
        name="Citizen Kumar"
    )

    # 2. Setup Complaint
    complaint = Complaint(
        ticket_id="DL-2026-TMLN01",
        citizen_name="Citizen Kumar",
        citizen_email="citizen_timeline@example.com",
        title="Water Supply Failure",
        description="No water for 2 days",
        category="WATER",
        department="DJB",
        district="West Delhi",
        status=ComplaintStatus.ASSIGNED
    )
    db_session.add(complaint)
    await db_session.commit()
    await db_session.refresh(complaint)

    # 3. Add Comments
    comment1 = Comment(complaint_id=complaint.id, user_id=citizen.id, message="Pls hurry")
    comment2 = Comment(complaint_id=complaint.id, user_id=officer.id, message="On it")
    db_session.add_all([comment1, comment2])

    # 4. Add Feedback
    feedback = Feedback(
        complaint_id=complaint.id,
        citizen_id=citizen.id,
        rating=5,
        note="Excellent fix!"
    )
    db_session.add(feedback)

    # 5. Add updates and attachments with matching time stamps (within 15s window)
    t0 = datetime.now(timezone.utc) - timedelta(minutes=30)
    t1 = datetime.now(timezone.utc) - timedelta(minutes=15)
    t2 = datetime.now(timezone.utc) - timedelta(minutes=5)

    update1 = ComplaintUpdate(
        complaint_id=complaint.id,
        status="SUBMITTED",
        note="Grievance received.",
        created_at=t0,
        updated_by=None
    )
    update2 = ComplaintUpdate(
        complaint_id=complaint.id,
        status="ASSIGNED",
        note="Officer assigned.",
        created_at=t1,
        updated_by=officer.id
    )
    update3 = ComplaintUpdate(
        complaint_id=complaint.id,
        status="RESOLVED",
        note="Leak fixed.",
        created_at=t2,
        updated_by=officer.id
    )
    db_session.add_all([update1, update2, update3])

    # Attachment proof linked to t2 (RESOLVED)
    attach = Attachment(
        complaint_id=complaint.id,
        file_url="/static/uploads/resolved_leak.png",
        created_at=t2 + timedelta(seconds=2) # 2 seconds after resolving
    )
    db_session.add(attach)
    await db_session.commit()
    
    # Reload complaint with relationships loaded
    from sqlalchemy.orm import selectinload
    from sqlalchemy.future import select
    stmt = (
        select(Complaint)
        .where(Complaint.id == complaint.id)
        .options(
            selectinload(Complaint.updates).selectinload(ComplaintUpdate.updater),
            selectinload(Complaint.attachments),
            selectinload(Complaint.comments),
            selectinload(Complaint.feedbacks)
        )
    )
    res = await db_session.execute(stmt)
    complaint_loaded = res.scalars().first()

    # 6. Serialize
    serialized = TimelineSerializationService.serialize_timeline(complaint_loaded)

    # 7. Assertions
    assert serialized["ticket_id"] == "DL-2026-TMLN01"
    assert serialized["current_status"] == "ASSIGNED"
    assert serialized["comment_count"] == 2
    assert serialized["feedback_submitted"] is True
    assert serialized["feedback_rating"] == 5
    assert serialized["feedback_remarks"] == "Excellent fix!"

    timeline = serialized["timeline"]
    assert len(timeline) == 3

    # Assert chronological order and details
    assert timeline[0]["status"] == "SUBMITTED"
    assert timeline[0]["color"] == "grey"
    assert timeline[0]["updated_by"] == "System"
    assert len(timeline[0]["proof_urls"]) == 0

    assert timeline[1]["status"] == "ASSIGNED"
    assert timeline[1]["color"] == "yellow"
    assert timeline[1]["updated_by"] == f"Officer ({officer.name})"
    assert len(timeline[1]["proof_urls"]) == 0

    assert timeline[2]["status"] == "RESOLVED"
    assert timeline[2]["color"] == "green"
    assert timeline[2]["updated_by"] == f"Officer ({officer.name})"
    # Proof url matched within 15 seconds!
    assert len(timeline[2]["proof_urls"]) == 1
    assert timeline[2]["proof_urls"][0] == "/static/uploads/resolved_leak.png"

@pytest.mark.asyncio
async def test_serialize_timeline_no_updates_fallback(db_session):
    complaint = Complaint(
        ticket_id="DL-2026-FALLBK",
        citizen_name="John",
        citizen_email="john@example.com",
        title="Sanitation Issue",
        description="Trash dump",
        category="SANITATION",
        department="MCD",
        district="North Delhi",
        status=ComplaintStatus.SUBMITTED
    )
    db_session.add(complaint)
    await db_session.commit()
    await db_session.refresh(complaint)

    # Serialize without updates
    serialized = TimelineSerializationService.serialize_timeline(complaint)

    assert serialized["ticket_id"] == "DL-2026-FALLBK"
    assert serialized["current_status"] == "SUBMITTED"
    assert len(serialized["timeline"]) == 1
    assert serialized["timeline"][0]["status"] == "SUBMITTED"
    assert serialized["timeline"][0]["color"] == "grey"
    assert serialized["timeline"][0]["updated_by"] == "System"

@pytest.mark.asyncio
async def test_serialize_timeline_unknown_status(db_session):
    complaint = Complaint(
        ticket_id="DL-2026-UNKWN1",
        citizen_name="John",
        citizen_email="john@example.com",
        title="Sanitation Issue",
        description="Trash dump",
        category="SANITATION",
        department="MCD",
        district="North Delhi",
        status=ComplaintStatus.SUBMITTED
    )
    db_session.add(complaint)
    await db_session.commit()
    await db_session.refresh(complaint)

    # Setup an update with an unknown status
    update = ComplaintUpdate(
        complaint_id=complaint.id,
        status="INVALID_STATUS_XYZ",
        note="Something strange happened.",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(update)
    await db_session.commit()

    # Load with updates
    from sqlalchemy.orm import selectinload
    from sqlalchemy.future import select
    stmt = (
        select(Complaint)
        .where(Complaint.id == complaint.id)
        .options(
            selectinload(Complaint.updates).selectinload(ComplaintUpdate.updater),
            selectinload(Complaint.attachments),
            selectinload(Complaint.comments),
            selectinload(Complaint.feedbacks)
        )
    )
    res = await db_session.execute(stmt)
    complaint_loaded = res.scalars().first()

    serialized = TimelineSerializationService.serialize_timeline(complaint_loaded)

    assert len(serialized["timeline"]) == 1
    assert serialized["timeline"][0]["status"] == "INVALID_STATUS_XYZ"
    assert serialized["timeline"][0]["color"] == "grey"  # default fallback
