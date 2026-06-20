import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import patch

@pytest.mark.asyncio
async def test_load_concurrent_submissions(async_client: AsyncClient):
    NUM_REQUESTS = 100
    
    # Payload factory to ensure unique emails and titles to bypass duplicate protection
    def get_payload(i: int):
        return {
            "citizen_name": f"User {i}",
            "citizen_email": f"user{i}@example.com",
            "citizen_phone": "9876543210",
            "title": f"Concurrent Issue {i}",
            "description": f"This is load test issue number {i}.",
            "district": "South Delhi",
            "category": "ROAD"
        }
        
    async def submit(i: int):
        with patch("app.api.routes.complaints.MLInferenceService") as mock_ml, \
             patch("app.api.routes.complaints.async_send_complaint_acknowledgement_email"):
            
            mock_inst = mock_ml.return_value
            mock_inst.predict.return_value = {"category_pred": ["ROAD"], "confidence_score": 0.9}
            mock_inst.predict_severity.return_value = "MEDIUM"
            
            res = await async_client.post("/api/v1/complaints/", data=get_payload(i))
            return res
            
    # Fire all 100 requests simultaneously
    responses = await asyncio.gather(*(submit(i) for i in range(NUM_REQUESTS)))
    
    ticket_ids = []
    failures = []
    
    for r in responses:
        if r.status_code == 201:
            ticket_ids.append(r.json()["ticket_id"])
        else:
            failures.append((r.status_code, r.text))
            
    # Verify no failures occurred
    assert len(failures) == 0, f"Some requests failed: {failures[:5]}"
    
    # Verify exactly 100 tickets created
    assert len(ticket_ids) == NUM_REQUESTS
    
    # Verify all ticket IDs are unique (No duplicate sequences)
    assert len(set(ticket_ids)) == NUM_REQUESTS, "Duplicate ticket IDs were generated due to race condition!"
