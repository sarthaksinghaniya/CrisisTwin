from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.session import engine

def init_db(db: Session) -> None:
    # Optional: Initial setup logic like creating a superuser if it doesn't exist
    pass
