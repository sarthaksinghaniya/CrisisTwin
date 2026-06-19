import os
import sys
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from jose import jwt

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CM-Dasboard')))

from app.db.session import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.models.otp import OTP
from app.core import security
from app.core.config import settings

# We will test the API directly using httpx AsyncClient
from httpx import AsyncClient
from app.main import app

# Mock class to return a fixed random number
class MockSystemRandom:
    def randint(self, a, b):
        return 123456

async def test_auth_cycle():
    print("Starting Email OTP Authentication integration test...")
    
    test_email = "new_citizen_test@delhi.gov.in"
    
    import httpx
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Clean up any existing records first
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            res_otp = await session.execute(select(OTP).filter(OTP.email == test_email))
            otp_record = res_otp.scalars().first()
            if otp_record:
                await session.delete(otp_record)
            res_user = await session.execute(select(User).filter(User.email == test_email))
            user = res_user.scalars().first()
            if user:
                await session.delete(user)
            await session.commit()

        # 1. Test POST /auth/request-otp with mock random generator
        print("\nStep 1: Requesting OTP for a new email address (mocked)...")
        with patch('secrets.SystemRandom', return_value=MockSystemRandom()):
            response = await client.post("/api/v1/auth/request-otp", json={"email": test_email})
            assert response.status_code == 200, f"Failed to request OTP: {response.text}"
            print(" -> Request-OTP response status: 200 OK")
        
        # 2. Verify auto-creation of citizen user
        async with AsyncSessionLocal() as session:
            res_user = await session.execute(select(User).filter(User.email == test_email))
            user = res_user.scalars().first()
            assert user is not None, "Citizen user was not auto-created!"
            assert user.role == RoleEnum.CITIZEN, f"Expected CITIZEN role, got {user.role}"
            print(f" -> Verified Citizen Auto-Creation: User ID={user.id}, Role={user.role.value}")
            
            # Retrieve the generated OTP from DB to verify it
            res_otp = await session.execute(select(OTP).filter(OTP.email == test_email))
            otp_record = res_otp.scalars().first()
            assert otp_record is not None, "OTP record not saved to database!"
            print(" -> Verified OTP record stored in database successfully.")
            
        # 3. Test verification failures & brute-force lockout (attempts max 5)
        print("\nStep 2: Testing failed verification attempts...")
        for i in range(1, 5):
            response = await client.post(
                "/api/v1/auth/verify-otp", 
                json={"email": test_email, "otp": "000000"} # incorrect OTP
            )
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            assert "Incorrect OTP code" in response.json()["detail"], f"Unexpected error detail: {response.json()}"
            print(f" -> Attempt {i} failed as expected. Log detail: {response.json()['detail']}")
            
        # The 5th failed attempt should trigger lockout
        print(" -> Dispatching 5th incorrect attempt to trigger lockout...")
        response = await client.post(
            "/api/v1/auth/verify-otp", 
            json={"email": test_email, "otp": "000000"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "locked out" in response.json()["detail"]
        print(" -> 5th attempt triggered lockout successfully.")
        
        # Verify that subsequent requests are locked out (returns 429)
        print(" -> Verifying lockout throttle throws 429 Too Many Requests...")
        response = await client.post("/api/v1/auth/request-otp", json={"email": test_email})
        assert response.status_code == 429, f"Expected 429, got {response.status_code}"
        assert "locked out" in response.json()["detail"]
        print(" -> Rate-limiting lockout verified successfully (Status: 429).")
        
        # 4. Clean up lockout state and test successful authentication
        print("\nStep 3: Resetting lockout state to test successful OTP validation...")
        async with AsyncSessionLocal() as session:
            res_otp = await session.execute(select(OTP).filter(OTP.email == test_email))
            otp_record = res_otp.scalars().first()
            if otp_record:
                await session.delete(otp_record)
            res_user = await session.execute(select(User).filter(User.email == test_email))
            user = res_user.scalars().first()
            if user:
                await session.delete(user)
            await session.commit()
            
        # Request OTP again (mocked to 123456)
        print(" -> Requesting new OTP (mocked to 123456)...")
        with patch('secrets.SystemRandom', return_value=MockSystemRandom()):
            response = await client.post("/api/v1/auth/request-otp", json={"email": test_email})
            assert response.status_code == 200
            
        # Verify correct OTP
        print(" -> Submitting correct verification payload (123456)...")
        response = await client.post(
            "/api/v1/auth/verify-otp", 
            json={"email": test_email, "otp": "123456"}
        )
        assert response.status_code == 200, f"Failed verification: {response.text}"
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        print(" -> Verification response status: 200 OK")
        print(" -> Issued Access Token successfully.")

        # Decode JWT and check claims
        payload = jwt.decode(token_data["access_token"], settings.SECRET_KEY, algorithms=["HS256"])
        print("\nStep 4: Decoding JWT and validating claims...")
        print(f" -> Decoded payload: {payload}")
        
        # Retrieve user ID to match sub
        async with AsyncSessionLocal() as session:
            res_user = await session.execute(select(User).filter(User.email == test_email))
            user = res_user.scalars().first()
            assert user is not None
            assert payload["sub"] == str(user.id), "JWT claim 'sub' does not match User ID"
            assert payload["email"] == test_email, "JWT claim 'email' does not match citizen email"
            assert payload["role"] == RoleEnum.CITIZEN.value, "JWT claim 'role' does not match RoleEnum.CITIZEN"
            print(" -> All claims validated successfully! (sub, email, role match)")

            # Check that OTP record was deleted on success
            res_otp = await session.execute(select(OTP).filter(OTP.email == test_email))
            otp_record = res_otp.scalars().first()
            assert otp_record is None, "OTP record was not deleted upon successful validation!"
            print(" -> Verified OTP table record was deleted on success.")
            
            # Clean up test user
            await session.delete(user)
            await session.commit()
            
    print("\nVerification completed successfully with no failures!")

if __name__ == "__main__":
    asyncio.run(test_auth_cycle())
