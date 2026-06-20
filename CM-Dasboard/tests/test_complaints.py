import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from io import BytesIO

from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.user import User, RoleEnum

# Mock ML response helper
def mock_ml_predict(category="ROAD", confidence=0.85):
    return {
        "category_pred": [category],
        "confidence_score": confidence
    }

@pytest.mark.asyncio
async def test_create_complaint_success_and_routed(
    async_client: AsyncClient, 
    db_session: AsyncSession,
    create_test_user
):
    # Create an officer in PWD, South Delhi
    officer = await create_test_user(
        email="pwd_officer@example.com",
        role=RoleEnum.OFFICER,
        department="PWD",
        district="South Delhi"
    )

    data = {
        "citizen_name": "John Doe",
        "citizen_email": "john.doe@example.com",
        "citizen_phone": "9876543210",
        "title": "Pothole on Main St",
        "description": "Large pothole causing traffic issues.",
        "district": "South Delhi",
        "category": "ROAD"
    }

    with patch("app.api.routes.complaints.MLInferenceService") as mock_ml_class, \
         patch("app.api.routes.complaints.async_send_complaint_acknowledgement_email"):
        
        mock_ml_instance = mock_ml_class.return_value
        mock_ml_instance.predict.return_value = mock_ml_predict("ROAD", 0.9)
        mock_ml_instance.predict_severity.return_value = "HIGH"
        
        response = await async_client.post("/api/v1/complaints/", data=data)
        
        assert response.status_code == 201
        res_data = response.json()
        assert "ticket_id" in res_data
        
        # Verify db assignment
        res = await db_session.execute(select(Complaint).filter(Complaint.ticket_id == res_data["ticket_id"]))
        complaint = res.scalars().first()
        assert complaint is not None
        assert complaint.assigned_to == officer.id

@pytest.mark.asyncio
async def test_create_duplicate_complaint(
    async_client: AsyncClient, 
    db_session: AsyncSession
):
    data = {
        "citizen_name": "Jane Doe",
        "citizen_email": "jane@example.com",
        "citizen_phone": "9876543211",
        "title": "Water Leak",
        "description": "Pipe broken",
        "district": "West Delhi",
        "category": "WATER"
    }
    
    with patch("app.api.routes.complaints.MLInferenceService") as mock_ml_class, \
         patch("app.api.routes.complaints.async_send_complaint_acknowledgement_email"):
        
        mock_ml_instance = mock_ml_class.return_value
        mock_ml_instance.predict.return_value = mock_ml_predict("WATER", 0.9)
        mock_ml_instance.predict_severity.return_value = "MEDIUM"

        # First submission
        res1 = await async_client.post("/api/v1/complaints/", data=data)
        assert res1.status_code == 201
        
        # Immediate second submission
        res2 = await async_client.post("/api/v1/complaints/", data=data)
        assert res2.status_code == 400
        assert "Duplicate complaint" in res2.json()["detail"]

@pytest.mark.asyncio
async def test_routing_head_fallback(
    async_client: AsyncClient, 
    db_session: AsyncSession,
    create_test_user
):
    # No officer available in district, but a department head exists
    head = await create_test_user(
        email="djb_head@example.com",
        role=RoleEnum.HEAD,
        department="DJB",
        district=None # Heads might not have district
    )
    
    data = {
        "citizen_name": "Jane Head",
        "citizen_email": "jane_head@example.com",
        "citizen_phone": "9876543211",
        "title": "Water Leak East Delhi",
        "description": "Pipe broken in East Delhi",
        "district": "East Delhi", # No officer here
        "category": "WATER"
    }
    
    with patch("app.api.routes.complaints.MLInferenceService") as mock_ml_class, \
         patch("app.api.routes.complaints.async_send_complaint_acknowledgement_email"):
        
        mock_ml_instance = mock_ml_class.return_value
        mock_ml_instance.predict.return_value = mock_ml_predict("WATER", 0.9)
        mock_ml_instance.predict_severity.return_value = "MEDIUM"
        
        res = await async_client.post("/api/v1/complaints/", data=data)
        assert res.status_code == 201
        ticket_id = res.json()["ticket_id"]
        
        db_res = await db_session.execute(select(Complaint).filter(Complaint.ticket_id == ticket_id))
        complaint = db_res.scalars().first()
        
        # Assigned to department head
        assert complaint.assigned_to == head.id

@pytest.mark.asyncio
async def test_routing_low_confidence_admin_queue(
    async_client: AsyncClient, 
    db_session: AsyncSession
):
    # Low confidence AI prediction -> should go to admin queue (assigned_to = None)
    data = {
        "citizen_name": "Test User",
        "citizen_email": "test@example.com",
        "citizen_phone": "9876543212",
        "title": "Unknown issue North Delhi",
        "description": "I have an issue but I don't know who to tell North Delhi.",
        "district": "North Delhi"
        # Omitting category to trigger AI
    }
    
    with patch("app.api.routes.complaints.MLInferenceService") as mock_ml_class, \
         patch("app.api.routes.complaints.async_send_complaint_acknowledgement_email"):
        
        mock_ml_instance = mock_ml_class.return_value
        # Mock low confidence
        mock_ml_instance.predict.return_value = mock_ml_predict("ROAD", 0.6)
        mock_ml_instance.predict_severity.return_value = "LOW"
        
        res = await async_client.post("/api/v1/complaints/", data=data)
        assert res.status_code == 201
        ticket_id = res.json()["ticket_id"]
        
        db_res = await db_session.execute(select(Complaint).filter(Complaint.ticket_id == ticket_id))
        complaint = db_res.scalars().first()
        
        # Assigned to None (Admin Review Queue)
        assert complaint.assigned_to is None
