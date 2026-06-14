from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Order, Transaction
from app.schemas.schemas import UserProfile, TransactionResponse, BalanceResponse

router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == int(current_user["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Count orders
    result = await db.execute(
        select(func.count(Order.id)).where(Order.user_id == user.id)
    )
    orders_count = result.scalar()
    
    # Total spent
    result = await db.execute(
        select(func.sum(Order.total_amount)).where(
            Order.user_id == user.id,
            Order.status == "completed"
        )
    )
    total_spent = result.scalar() or 0.0
    
    return UserProfile(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_admin=user.is_admin,
        is_blocked=user.is_blocked,
        balance=user.balance,
        referral_code=user.referral_code,
        referral_bonus_earned=user.referral_bonus_earned,
        created_at=user.created_at,
        orders_count=orders_count,
        total_spent=round(total_spent, 2),
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == int(current_user["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return BalanceResponse(currency="UZS", balance=round(user.balance, 2))


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == int(current_user["sub"]))
        .order_by(Transaction.created_at.desc())
    )
    return result.scalars().all()


@router.get("/referral-link")
async def get_referral_link(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == int(current_user["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    bot_username = settings.BOT_USERNAME or "your_bot_username"
    return {
        "link": f"https://t.me/{bot_username}?start=ref_{user.telegram_id}",
        "code": user.referral_code,
        "bonus_earned": user.referral_bonus_earned,
    }
