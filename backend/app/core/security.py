import hmac
import hashlib
import time
import json
from typing import Optional
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.models.models import User

security_bearer = HTTPBearer(auto_error=False)


def generate_telegram_auth_signature(payload: dict, path: str, secret: str, timestamp: int = None) -> tuple[int, str]:
    """Generate MooGold-style auth signature."""
    if timestamp is None:
        timestamp = int(time.time())
    
    # Compact JSON payload (no spaces, sorted keys)
    payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    
    # Signature string: Payload + Timestamp + Path
    string_to_sign = f"{payload_str}{timestamp}{path}"
    
    signature = hmac.new(
        secret.encode(),
        string_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return timestamp, signature


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram WebApp InitData HMAC."""
    from urllib.parse import parse_qsl
    
    data = dict(parse_qsl(init_data))
    received_hash = data.pop("hash", "")
    
    # Create data_check_string
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )
    
    # Create secret_key from bot_token
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram InitData"
        )
    
    # Check auth_date freshness (max 24 hours)
    auth_date = int(data.get("auth_date", 0))
    if int(time.time()) - auth_date > 86400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram InitData expired"
        )
    
    return data


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )

    token = credentials.credentials
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    # Re-check user on every protected request so blocked/deleted users lose access immediately.
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    if db_user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is blocked"
        )

    return payload


async def get_current_admin(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    # Re-check admin status from database (token may be stale)
    result = await db.execute(select(User).where(User.id == int(user["sub"])))
    db_user = result.scalar_one_or_none()
    if not db_user or not db_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
