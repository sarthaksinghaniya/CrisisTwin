from sqlalchemy.orm import Session
from app.models.crisis import Crisis
from app.schemas.crisis import CrisisCreate, CrisisUpdate

def get_crisis(db: Session, crisis_id: int):
    return db.query(Crisis).filter(Crisis.id == crisis_id).first()

def get_crises(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Crisis).offset(skip).limit(limit).all()

def create_crisis(db: Session, obj_in: CrisisCreate, user_id: int):
    db_obj = Crisis(
        **obj_in.model_dump(),
        created_by=user_id
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_crisis(db: Session, db_obj: Crisis, obj_in: CrisisUpdate):
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def delete_crisis(db: Session, crisis_id: int):
    db_obj = db.query(Crisis).filter(Crisis.id == crisis_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj
