from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import crisis as crud_crisis
from app.schemas.crisis import Crisis, CrisisCreate, CrisisUpdate
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=Crisis)
def create_crisis(
    *,
    db: Session = Depends(deps.get_db),
    crisis_in: CrisisCreate,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Create new crisis.
    """
    crisis = crud_crisis.create_crisis(db=db, obj_in=crisis_in, user_id=current_user.id)
    return crisis

@router.get("/", response_model=List[Crisis])
def read_crises(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Retrieve crises.
    """
    crises = crud_crisis.get_crises(db=db, skip=skip, limit=limit)
    return crises

@router.get("/{id}", response_model=Crisis)
def read_crisis(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get crisis by ID.
    """
    crisis = crud_crisis.get_crisis(db=db, crisis_id=id)
    if not crisis:
        raise HTTPException(status_code=404, detail="Crisis not found")
    return crisis

@router.put("/{id}", response_model=Crisis)
def update_crisis(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    crisis_in: CrisisUpdate,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Update a crisis.
    """
    crisis = crud_crisis.get_crisis(db=db, crisis_id=id)
    if not crisis:
        raise HTTPException(status_code=404, detail="Crisis not found")
    
    crisis = crud_crisis.update_crisis(db=db, db_obj=crisis, obj_in=crisis_in)
    return crisis

@router.delete("/{id}", response_model=Crisis)
def delete_crisis(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Delete a crisis.
    """
    crisis = crud_crisis.get_crisis(db=db, crisis_id=id)
    if not crisis:
        raise HTTPException(status_code=404, detail="Crisis not found")
    
    crisis = crud_crisis.delete_crisis(db=db, crisis_id=id)
    return crisis
