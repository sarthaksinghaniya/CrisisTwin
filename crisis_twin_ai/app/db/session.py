from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# --- Sync Configuration ---
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Sync dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Async Configuration (Ready for future use) ---
# Note: You will need to install the async driver: pip install asyncpg
async_engine = create_async_engine(settings.SQLALCHEMY_ASYNC_DATABASE_URI, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession)

async def get_async_db():
    """Async dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        yield session
