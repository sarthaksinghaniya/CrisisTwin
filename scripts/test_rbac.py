import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from jose import jwt

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CM-Dasboard')))

from app.db.session import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.core import security
from app.core.config import settings

# Test using httpx AsyncClient
from httpx import AsyncClient
from app.main import app
from fastapi import APIRouter, Depends
from app.api.deps import require_role, Admin, Officer, Head, Citizen, get_current_user

# Create dynamic test router to run HTTP tests against the dependency check
test_router = APIRouter(prefix="/api/v1/test-rbac", tags=["test-rbac"])

@test_router.get("/admin", dependencies=[Depends(require_role(Admin))])
async def admin_only():
    return {"message": "Welcome, Admin!"}

@test_router.get("/officer", dependencies=[Depends(require_role(Officer))])
async def officer_only():
    return {"message": "Welcome, Officer!"}

@test_router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role}

app.include_router(test_router)

async def test_rbac_flow():
    print("Starting JWT Role-Based Access Control (RBAC) integration tests...")

    # Test emails
    emails = {
        "citizen": "test_citizen@delhi.gov.in",
        "officer": "test_officer@delhi.gov.in",
        "head": "test_head@delhi.gov.in",
        "admin": "test_admin@delhi.gov.in"
    }

    # 1. Clean up existing test users if any
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        for email in emails.values():
            res_user = await session.execute(select(User).filter(User.email == email))
            user = res_user.scalars().first()
            if user:
                await session.delete(user)
        await session.commit()
        print(" -> Cleaned up old test users.")

    # 2. Create the 4 users
    user_ids = {}
    async with AsyncSessionLocal() as session:
        for role_name, email in emails.items():
            role_enum = getattr(RoleEnum, role_name.upper())
            user = User(
                name=f"Test {role_name.capitalize()}",
                email=email,
                role=role_enum,
                is_deleted=False
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_ids[role_name] = user.id
            print(f" -> Created user: {email} with ID: {user.id} and Role: {user.role.value}")

    # 3. Generate Valid Tokens
    tokens = {}
    for role_name, email in emails.items():
        user_id = user_ids[role_name]
        role_enum = getattr(RoleEnum, role_name.upper())
        token = security.create_access_token(
            subject=user_id,
            email=email,
            role=role_enum.value
        )
        tokens[role_name] = token
        print(f" -> Generated token for {role_name}.")

    import httpx
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # --- Test 1: Access Admin resource with Citizen Token (Should be 403 Forbidden) ---
        print("\nTest 1: Citizen access to Admin endpoint...")
        headers = {"Authorization": f"Bearer {tokens['citizen']}"}
        response = await client.get("/api/v1/test-rbac/admin", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        assert "Permission denied. Role 'ADMIN' required." in response.json()["detail"]
        print(" -> PASSED: Citizen access denied with 403 Forbidden.")

        # --- Test 2: Access Admin resource with Admin Token (Should be 200 OK) ---
        print("\nTest 2: Admin access to Admin endpoint...")
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        response = await client.get("/api/v1/test-rbac/admin", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.json()["message"] == "Welcome, Admin!"
        print(" -> PASSED: Admin access granted with 200 OK.")

        # --- Test 3: Access Officer resource with Officer Token (Should be 200 OK) ---
        print("\nTest 3: Officer access to Officer endpoint...")
        headers = {"Authorization": f"Bearer {tokens['officer']}"}
        response = await client.get("/api/v1/test-rbac/officer", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.json()["message"] == "Welcome, Officer!"
        print(" -> PASSED: Officer access granted with 200 OK.")

        # --- Test 4: Access with missing/invalid Authorization Header ---
        print("\nTest 4: Request with missing Authorization header...")
        response = await client.get("/api/v1/test-rbac/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "Missing Authorization Header" in response.json()["detail"]
        print(" -> PASSED: Missing header raises 401 Unauthorized.")

        print(" -> Request with non-Bearer scheme...")
        response = await client.get("/api/v1/test-rbac/me", headers={"Authorization": f"Basic {tokens['citizen']}"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "Invalid authentication scheme. Bearer expected." in response.json()["detail"]
        print(" -> PASSED: Non-Bearer scheme raises 401 Unauthorized.")

        # --- Test 5: Expired Token ---
        print("\nTest 5: Request with expired token...")
        expired_token = security.create_access_token(
            subject=user_ids["citizen"],
            email=emails["citizen"],
            role=RoleEnum.CITIZEN.value,
            expires_delta=timedelta(minutes=-5) # expired 5 mins ago
        )
        response = await client.get("/api/v1/test-rbac/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "Token has expired" in response.json()["detail"]
        print(" -> PASSED: Expired token raises 401 Unauthorized.")

        # --- Test 6: Tampered Token (signature modified) ---
        print("\nTest 6: Request with tampered token...")
        tampered_token = tokens["citizen"] + "a" # append character to break signature verification
        response = await client.get("/api/v1/test-rbac/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "Invalid or tampered authentication token" in response.json()["detail"]
        print(" -> PASSED: Tampered token raises 401 Unauthorized.")

        # --- Test 7: Wrong Signature Key ---
        print("\nTest 7: Request with token signed using wrong secret...")
        wrong_secret_token = jwt.encode(
            {
                "exp": datetime.utcnow() + timedelta(minutes=60),
                "sub": str(user_ids["citizen"]),
                "email": emails["citizen"],
                "role": RoleEnum.CITIZEN.value
            },
            "WRONG_SECRET_KEY_12345",
            algorithm="HS256"
        )
        response = await client.get("/api/v1/test-rbac/me", headers={"Authorization": f"Bearer {wrong_secret_token}"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "Invalid or tampered authentication token" in response.json()["detail"]
        print(" -> PASSED: Wrong signature key raises 401 Unauthorized.")

        # --- Test 8: Deactivated (soft deleted) user ---
        print("\nTest 8: Request from deactivated (soft deleted) user...")
        async with AsyncSessionLocal() as session:
            res_user = await session.execute(select(User).filter(User.id == user_ids["citizen"]))
            user = res_user.scalars().first()
            user.is_deleted = True
            await session.commit()
            print(" -> Marked citizen user as is_deleted = True.")

        response = await client.get("/api/v1/test-rbac/me", headers={"Authorization": f"Bearer {tokens['citizen']}"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        assert "User account is deactivated" in response.json()["detail"]
        print(" -> PASSED: Soft-deleted user raises 401 Unauthorized.")

        # --- Test 9: Deleted user ---
        print("\nTest 9: Request from fully deleted user...")
        async with AsyncSessionLocal() as session:
            res_user = await session.execute(select(User).filter(User.id == user_ids["citizen"]))
            user = res_user.scalars().first()
            await session.delete(user)
            await session.commit()
            print(" -> Deleted citizen user from database.")

        response = await client.get("/api/v1/test-rbac/me", headers={"Authorization": f"Bearer {tokens['citizen']}"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        assert "User account has been deleted" in response.json()["detail"]
        print(" -> PASSED: Deleted user raises 401 Unauthorized.")

    # Cleanup remaining users
    async with AsyncSessionLocal() as session:
        for role_name, email in emails.items():
            if role_name == "citizen":
                continue # Already deleted in Test 9
            res_user = await session.execute(select(User).filter(User.email == email))
            user = res_user.scalars().first()
            if user:
                await session.delete(user)
        await session.commit()
        print(" -> Cleaned up remaining test users.")

    print("\nAll RBAC and Token validation tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_rbac_flow())
