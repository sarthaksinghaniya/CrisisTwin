import pytest
from httpx import AsyncClient
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.otp import OTP
from app.models.user import User
from app.core import security

@pytest.mark.asyncio
async def test_request_otp_success(async_client: AsyncClient, db_session: AsyncSession):
    email = "newuser@example.com"
    with patch("app.api.routes.auth.async_send_otp_email") as mock_send_email:
        mock_send_email.return_value = None
        
        response = await async_client.post(
            "/api/v1/auth/request-otp",
            json={"email": email}
        )
        
        assert response.status_code == 200
        assert "dispatched to email" in response.json()["message"]
        
        # Verify user created
        res = await db_session.execute(select(User).filter(User.email == email))
        user = res.scalars().first()
        assert user is not None
        assert user.email == email
        
        # Verify OTP record created
        res = await db_session.execute(select(OTP).filter(OTP.email == email))
        otp_record = res.scalars().first()
        assert otp_record is not None
        assert otp_record.attempts == 0

@pytest.mark.asyncio
async def test_verify_otp_success(async_client: AsyncClient, db_session: AsyncSession):
    email = "verify@example.com"
    otp_code = "123456"
    hashed_otp = security.get_password_hash(otp_code)
    
    # Setup user and OTP
    user = User(name="Test", email=email, role="CITIZEN")
    db_session.add(user)
    
    otp_record = OTP(
        email=email,
        otp_hash=hashed_otp,
        expiry=datetime.utcnow() + timedelta(minutes=4),
        attempts=0,
        created_at=datetime.utcnow()
    )
    db_session.add(otp_record)
    await db_session.commit()
    
    response = await async_client.post(
        "/api/v1/auth/verify-otp",
        json={"email": email, "otp": otp_code}
    )
    
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"
    
    # Verify OTP record is deleted
    res = await db_session.execute(select(OTP).filter(OTP.email == email))
    assert res.scalars().first() is None

@pytest.mark.asyncio
async def test_verify_otp_invalid(async_client: AsyncClient, db_session: AsyncSession):
    email = "invalid@example.com"
    otp_code = "123456"
    hashed_otp = security.get_password_hash(otp_code)
    
    otp_record = OTP(
        email=email,
        otp_hash=hashed_otp,
        expiry=datetime.utcnow() + timedelta(minutes=4),
        attempts=0,
        created_at=datetime.utcnow()
    )
    db_session.add(otp_record)
    await db_session.commit()
    
    response = await async_client.post(
        "/api/v1/auth/verify-otp",
        json={"email": email, "otp": "000000"} # Wrong OTP
    )
    
    assert response.status_code == 400
    assert "Incorrect OTP" in response.json()["detail"]
    
    # Verify attempts incremented
    await db_session.refresh(otp_record)
    assert otp_record.attempts == 1

@pytest.mark.asyncio
async def test_verify_otp_expiry(async_client: AsyncClient, db_session: AsyncSession):
    email = "expired@example.com"
    otp_code = "123456"
    hashed_otp = security.get_password_hash(otp_code)
    
    otp_record = OTP(
        email=email,
        otp_hash=hashed_otp,
        expiry=datetime.utcnow() - timedelta(minutes=1), # Expired
        attempts=0,
        created_at=datetime.utcnow() - timedelta(minutes=5)
    )
    db_session.add(otp_record)
    await db_session.commit()
    
    response = await async_client.post(
        "/api/v1/auth/verify-otp",
        json={"email": email, "otp": otp_code}
    )
    
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_verify_otp_bruteforce_lockout(async_client: AsyncClient, db_session: AsyncSession):
    email = "lockout@example.com"
    otp_code = "123456"
    hashed_otp = security.get_password_hash(otp_code)
    
    otp_record = OTP(
        email=email,
        otp_hash=hashed_otp,
        expiry=datetime.utcnow() + timedelta(minutes=4),
        attempts=4, # One attempt away from lockout
        created_at=datetime.utcnow()
    )
    db_session.add(otp_record)
    await db_session.commit()
    
    # 5th failed attempt (should lock out)
    response = await async_client.post(
        "/api/v1/auth/verify-otp",
        json={"email": email, "otp": "000000"}
    )
    
    assert response.status_code == 400
    assert "Account locked out" in response.json()["detail"]
    
    # Subsequent attempt within 15 minutes should fail with 429
    response_locked = await async_client.post(
        "/api/v1/auth/request-otp",
        json={"email": email}
    )
    
    assert response_locked.status_code == 429
    assert "Account locked out" in response_locked.json()["detail"]
