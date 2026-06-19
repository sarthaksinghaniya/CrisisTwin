from typing import Annotated, Any, Union
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.config import settings
from app.core import security
from app.db.session import get_db
from app.models.user import User, RoleEnum
from app.schemas.token import TokenPayload

# Define HTTPBearer security scheme directly to control authentication error details
security_scheme = HTTPBearer(auto_error=False)

# Define Role Class Stubs
class Citizen:
    pass

class Officer:
    pass

class Head:
    pass

class Admin:
    pass

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)]

async def get_current_user(db: SessionDep, token_credentials: TokenDep) -> User:
    # 1. Check if token credentials are provided
    if not token_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Check token schema is Bearer
    if token_credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Bearer expected.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = token_credentials.credentials
    try:
        # 3. Decode and validate JWT
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or tampered authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 4. Check subject claim (User ID) exists
    if not token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 5. Retrieve user and verify database state (Edge Case: deleted/deactivated user)
    result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

class RoleChecker:
    """
    Dependency callable that validates the logged-in user's role against the required role.
    """
    def __init__(self, required_role: Any):
        self.required_role = required_role

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        # Map class stubs, string keys, and RoleEnum types to standard strings
        if isinstance(self.required_role, type):
            target_role = self.required_role.__name__.upper()
        elif isinstance(self.required_role, RoleEnum):
            target_role = self.required_role.value
        else:
            target_role = str(self.required_role).upper()
            
        user_role = current_user.role.value
        
        # Check strict role authorization
        if user_role != target_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Role '{target_role}' required."
            )
            
        return current_user

def require_role(required_role: Any):
    """
    FastAPI dependency factory to enforce Role-Based Access Control.
    Usage: Depends(require_role(Admin))
    """
    return RoleChecker(required_role)
