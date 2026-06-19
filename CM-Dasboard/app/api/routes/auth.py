import secrets
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.models.user import User, RoleEnum
from app.models.otp import OTP
from app.schemas.auth import OTPRequest, OTPVerify
from app.schemas.token import Token
from app.core import security
from app.core.config import settings
from app.services.email.smtp import async_send_otp_email

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def request_otp(
    payload: OTPRequest,
    db: AsyncSession = Depends(get_db)
):
    email = payload.email.lower().strip()
    
    # 1. Check existing OTP record for lockout state
    res = await db.execute(select(OTP).filter(OTP.email == email))
    otp_record = res.scalars().first()
    
    now = datetime.now(timezone.utc)
    
    if otp_record and otp_record.attempts >= 5:
        # Check if 15 minute lockout window is still active
        lockout_expiry = otp_record.created_at + timedelta(minutes=15)
        if now < lockout_expiry:
            remaining_minutes = int((lockout_expiry - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many verification failures. Account locked out. Try again in {remaining_minutes} minutes."
            )
        else:
            # Lockout period expired; reset efforts
            otp_record.attempts = 0
            await db.commit()
            
    # 2. Check/Auto-Create Citizen User
    res_user = await db.execute(select(User).filter(User.email == email))
    user = res_user.scalars().first()
    
    if not user:
        logger.info(f"Auto-creating citizen user for email: {email}")
        user = User(
            name=email.split("@")[0].title(),
            email=email,
            role=RoleEnum.CITIZEN
        )
        try:
            db.add(user)
            await db.commit()
            await db.refresh(user)
        except IntegrityError:
            await db.rollback()
            # Parallel request created the user; fetch it
            res_user = await db.execute(select(User).filter(User.email == email))
            user = res_user.scalars().first()
            
    # 3. Generate Cryptographically Secure 6-digit OTP
    # SystemRandom is cryptographically secure
    otp_code = f"{secrets.SystemRandom().randint(100000, 999999):06d}"
    hashed_otp = security.get_password_hash(otp_code)
    
    # 4. Upsert OTP record
    if not otp_record:
        otp_record = OTP(
            email=email,
            otp_hash=hashed_otp,
            expiry=now + timedelta(minutes=4),
            attempts=0,
            created_at=now
        )
        db.add(otp_record)
    else:
        otp_record.otp_hash = hashed_otp
        otp_record.expiry = now + timedelta(minutes=4)
        otp_record.attempts = 0
        otp_record.created_at = now
        
    await db.commit()
    
    # 5. Send SMTP Email (Async thread wrapper)
    try:
        await async_send_otp_email(email, otp_code)
    except Exception as e:
        logger.error(f"Failed to deliver OTP email to {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send OTP verification email. Please check your credentials or try again later."
        )
        
    return {"status": "success", "message": "OTP verification code dispatched to email."}

@router.post("/verify-otp", response_model=Token)
async def verify_otp(
    payload: OTPVerify,
    db: AsyncSession = Depends(get_db)
):
    email = payload.email.lower().strip()
    
    # 1. Fetch OTP record
    res = await db.execute(select(OTP).filter(OTP.email == email))
    otp_record = res.scalars().first()
    
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP verification code has not been requested or has expired."
        )
        
    now = datetime.now(timezone.utc)
    
    # 2. Check Lockout State
    if otp_record.attempts >= 5:
        lockout_expiry = otp_record.created_at + timedelta(minutes=15)
        if now < lockout_expiry:
            remaining_minutes = int((lockout_expiry - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUEST,
                detail=f"Account is locked out due to too many failed attempts. Try again in {remaining_minutes} minutes."
            )
        else:
            # Reset attempts if lockout expired
            otp_record.attempts = 0
            await db.commit()
            
    # 3. Check Expiry
    if now > otp_record.expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP verification code has expired. Please request a new code."
        )
        
    # 4. Verify OTP Hash
    if not security.verify_password(payload.otp, otp_record.otp_hash):
        otp_record.attempts += 1
        
        # If max attempts reached, trigger lockout start (save current timestamp)
        if otp_record.attempts >= 5:
            otp_record.created_at = now
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect OTP. Too many failed attempts. Account locked out for 15 minutes."
            )
        else:
            await db.commit()
            remaining_attempts = 5 - otp_record.attempts
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Incorrect OTP code. {remaining_attempts} attempts remaining."
            )
            
    # 5. Success - Fetch User Profile
    res_user = await db.execute(select(User).filter(User.email == email))
    user = res_user.scalars().first()
    
    if not user:
        # Fallback creation just in case
        user = User(
            name=email.split("@")[0].title(),
            email=email,
            role=RoleEnum.CITIZEN
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
    # 6. Delete OTP record from database
    await db.delete(otp_record)
    await db.commit()
    
    # 7. Issue JWT Token with Claims
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(
        subject=user.id,
        email=user.email,
        role=user.role.value,
        expires_delta=access_token_expires
    )
    
    return Token(access_token=token, token_type="bearer")
