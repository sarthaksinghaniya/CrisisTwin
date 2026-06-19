from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentUpdate, IncidentResponse
from pydantic import BaseModel
from celery.result import AsyncResult
from app.tasks.pipeline_task import run_incident_pipeline
from app.worker.celery_app import celery_app

class AnalyzeRequest(BaseModel):
    text: str

router = APIRouter()

@router.post("/", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(incident_in: IncidentCreate, db: AsyncSession = Depends(get_db)):
    incident = Incident(**incident_in.model_dump())
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident

@router.get("/{incident_id}", response_model=IncidentResponse)
async def read_incident(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).filter(Incident.id == incident_id))
    incident = result.scalars().first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident

@router.get("/", response_model=List[IncidentResponse])
async def list_incidents(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(incident_id: UUID, incident_in: IncidentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).filter(Incident.id == incident_id))
    incident = result.scalars().first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    update_data = incident_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(incident, field, value)
        
    await db.commit()
    await db.refresh(incident)
    return incident

@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).filter(Incident.id == incident_id))
    incident = result.scalars().first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    await db.delete(incident)
    await db.commit()

@router.post("/analyze")
async def analyze_incident_async(request: AnalyzeRequest):
    # Dispatch to Celery background task
    task = run_incident_pipeline.delay(request.text)
    return {"task_id": task.id, "status": "Processing"}

@router.get("/analyze/{task_id}")
async def get_analyze_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    result = {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None
    }
    return result
