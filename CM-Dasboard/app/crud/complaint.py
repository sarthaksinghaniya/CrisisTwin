from sqlalchemy.orm import Session
from app.models.complaint import Complaint
from app.schemas.complaint import CrisisCreate, CrisisUpdate

def get_complaint(db: Session, complaint_id: int):
    return db.query(Complaint).filter(Complaint.id == complaint_id).first()

def get_crises(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Complaint).offset(skip).limit(limit).all()

def create_complaint(db: Session, obj_in: CrisisCreate, user_id: int):
    db_obj = Complaint(
        **obj_in.model_dump(),
        created_by=user_id
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_complaint(db: Session, db_obj: Complaint, obj_in: CrisisUpdate):
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def delete_complaint(db: Session, complaint_id: int):
    db_obj = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj
