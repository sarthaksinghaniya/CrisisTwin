import socketio
import logging
from jose import jwt, JWTError
from app.core import security
from app.core.config import settings

logger = logging.getLogger("cm_dashboard.socket")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

@sio.on("connect")
async def connect(sid, environ, auth):
    try:
        if not auth or "token" not in auth:
            logger.warning(f"Socket connection rejected: No token provided (sid: {sid})")
            raise socketio.exceptions.ConnectionRefusedError("unauthorized")
            
        token = auth["token"]
        
        # Verify Token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role", "").upper()
        
        if not user_id:
            raise socketio.exceptions.ConnectionRefusedError("unauthorized")
            
        # Save session data
        async with sio.session(sid) as session:
            session["user_id"] = user_id
            session["role"] = role
            
        # Join user-specific room
        await sio.enter_room(sid, user_id)
        
        # Join admin broadcast room
        if role == "ADMIN":
            await sio.enter_room(sid, "admins")
            
        logger.info(f"Socket connected: {sid} (User: {user_id}, Role: {role})")
        
    except JWTError as e:
        logger.warning(f"Socket connection rejected: Invalid token ({e})")
        raise socketio.exceptions.ConnectionRefusedError("unauthorized")
    except Exception as e:
        logger.error(f"Socket connection error: {e}", exc_info=True)
        raise socketio.exceptions.ConnectionRefusedError("unauthorized")

@sio.on("disconnect")
async def disconnect(sid):
    logger.info(f"Socket disconnected: {sid}")
