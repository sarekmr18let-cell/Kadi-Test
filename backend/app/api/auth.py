from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    verify_telegram_init_data,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.models.models import User
from app.schemas.schemas import (
    TelegramAuthRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
)

router = APIRouter()


@router.post("/telegram", response_model=TokenResponse)
@limiter.limit("5/minute")
async def telegram_auth(
    request: Request,
    auth_request: TelegramAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user via Telegram WebApp InitData."""
    try:
        init_data = verify_telegram_init_data(auth_request.init_data, settings.BOT_TOKEN)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid init data: {str(e)}"
        )
    
    # Parse user data from init_data
    import json
    user_data = json.loads(init_data.get("user", "{}"))
    
    telegram_id = int(user_data.get("id", 0))
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram ID not found in init data"
        )
    
    # Find or create user
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=user_data.get("username"),
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            referral_code=f"REF{telegram_id}",
        )
        db.add(user)
        await db.flush()
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is blocked"
        )
    
    # Generate tokens
    token_data = {
        "sub": str(user.id),
        "telegram_id": user.telegram_id,
        "username": user.username,
        "is_admin": user.is_admin,
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    await db.commit()
    
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token."""
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    result = await db.execute(select(User).where(User.id == int(payload.get("sub"))))
    user = result.scalar_one_or_none()
    if not user or user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active"
        )

    token_data = {
        "sub": str(user.id),
        "telegram_id": user.telegram_id,
        "username": user.username,
        "is_admin": user.is_admin,
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get current user info."""
    result = await db.execute(select(User).where(User.id == int(current_user["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
