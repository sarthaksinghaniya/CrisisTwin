from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.assignment import Assignment
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentResponse

router = APIRouter()

@router.post("/", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(assignment_in: AssignmentCreate, db: AsyncSession = Depends(get_db)):
    assignment = Assignment(**assignment_in.model_dump())
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment

@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def read_assignment(assignment_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Assignment).filter(Assignment.id == assignment_id))
    assignment = result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment

@router.get("/", response_model=List[AssignmentResponse])
async def list_assignments(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Assignment).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(assignment_id: UUID, assignment_in: AssignmentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Assignment).filter(Assignment.id == assignment_id))
    assignment = result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    update_data = assignment_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assignment, field, value)
        
    await db.commit()
    await db.refresh(assignment)
    return assignment

@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Assignment).filter(Assignment.id == assignment_id))
    assignment = result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    await db.delete(assignment)
    await db.commit()
