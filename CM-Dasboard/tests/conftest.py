import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import asyncio
from typing import AsyncGenerator
from sqlalchemy.pool import NullPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings
from app.models.user import User, RoleEnum
from app.core.security import create_access_token

TEST_SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db" if settings.USE_SQLITE.lower() == "true" else "postgresql+asyncpg://postgres:anubhav2004@localhost:5432/cm_dashboard_test"

engine = create_async_engine(TEST_SQLALCHEMY_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)



@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    # Create test database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture()
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    # Override dependency
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
        
    # Clear overrides
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def create_test_user(db_session: AsyncSession):
    async def _create_test_user(
        email="test@example.com", 
        role=RoleEnum.CITIZEN,
        department=None,
        district=None,
        name="Test User"
    ) -> User:
        user = User(
            email=email,
            name=name,
            role=role,
            department=department,
            district=district
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    return _create_test_user

@pytest_asyncio.fixture
async def auth_headers(create_test_user):
    async def _auth_headers(user: User = None, role: RoleEnum = RoleEnum.CITIZEN):
        if not user:
            user = await create_test_user(email=f"auth_{role.value}@example.com", role=role)
        token = create_access_token(user.id, user.email, role.value)
        return {"Authorization": f"Bearer {token}"}
    return _auth_headers
