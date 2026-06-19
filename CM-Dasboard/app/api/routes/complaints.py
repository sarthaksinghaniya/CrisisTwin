from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import complaint as crud_complaint
from app.schemas.complaint import Complaint, CrisisCreate, CrisisUpdate
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=Complaint)
def create_complaint(
    *,
    db: Session = Depends(deps.get_db),
    complaint_in: CrisisCreate,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Create new complaint.
    """
    complaint = crud_complaint.create_complaint(db=db, obj_in=complaint_in, user_id=current_user.id)
    return complaint

@router.get("/", response_model=List[Complaint])
def read_crises(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Retrieve complaints.
    """
    complaints = crud_complaint.get_crises(db=db, skip=skip, limit=limit)
    return complaints

@router.get("/{id}", response_model=Complaint)
def read_complaint(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get complaint by ID.
    """
    complaint = crud_complaint.get_complaint(db=db, complaint_id=id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint

@router.put("/{id}", response_model=Complaint)
def update_complaint(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    complaint_in: CrisisUpdate,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Update a complaint.
    """
    complaint = crud_complaint.get_complaint(db=db, complaint_id=id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    complaint = crud_complaint.update_complaint(db=db, db_obj=complaint, obj_in=complaint_in)
    return complaint

@router.delete("/{id}", response_model=Complaint)
def delete_complaint(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Delete a complaint.
    """
    complaint = crud_complaint.get_complaint(db=db, complaint_id=id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    complaint = crud_complaint.delete_complaint(db=db, complaint_id=id)
    return complaint
