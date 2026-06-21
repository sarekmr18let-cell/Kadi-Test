from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List

from app.core.config import settings
from app.core.database import get_db
from app.models.models import User, Order, OrderItem, ProductVariation
from app.schemas.schemas import UserProfile, OrderResponse, BalanceResponse

router = APIRouter()


class ReferralRequest(BaseModel):
    telegram_id: int
    referrer_id: int


def verify_internal_bot_secret(x_bot_secret: Optional[str] = Header(None, alias="X-Bot-Secret")) -> None:
    """Protect bot-only endpoints from public access."""
    if not settings.INTERNAL_BOT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_BOT_SECRET is not configured",
        )
    if not x_bot_secret or x_bot_secret != settings.INTERNAL_BOT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal bot secret",
        )


async def get_user_by_telegram_id(telegram_id: int, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Open the Mini App once first.")
    if user.is_blocked:
        raise HTTPException(status_code=403, detail="User is blocked")
    return user


@router.get("/profile/{telegram_id}", response_model=UserProfile, dependencies=[Depends(verify_internal_bot_secret)])
async def get_profile_for_bot(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(telegram_id, db)

    result = await db.execute(select(func.count(Order.id)).where(Order.user_id == user.id))
    orders_count = result.scalar() or 0

    result = await db.execute(
        select(func.sum(Order.total_amount)).where(
            Order.user_id == user.id,
            Order.status == "completed",
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


@router.get("/orders/{telegram_id}", response_model=List[OrderResponse], dependencies=[Depends(verify_internal_bot_secret)])
async def get_orders_for_bot(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(telegram_id, db)
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.variation).selectinload(ProductVariation.product))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(10)
    )
    return result.scalars().all()


@router.get("/balance/{telegram_id}", response_model=BalanceResponse, dependencies=[Depends(verify_internal_bot_secret)])
async def get_balance_for_bot(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(telegram_id, db)
    return BalanceResponse(currency="UZS", balance=round(user.balance, 2))


@router.post("/referral", dependencies=[Depends(verify_internal_bot_secret)])
async def register_referral_for_bot(request: ReferralRequest, db: AsyncSession = Depends(get_db)):
    if request.telegram_id == request.referrer_id:
        return {"status": "ignored", "reason": "self referral"}

    user_result = await db.execute(select(User).where(User.telegram_id == request.telegram_id))
    user = user_result.scalar_one_or_none()
    referrer_result = await db.execute(select(User).where(User.telegram_id == request.referrer_id))
    referrer = referrer_result.scalar_one_or_none()

    if not user or not referrer:
        return {"status": "ignored", "reason": "user or referrer not found"}

    if user.referrer_id is None:
        user.referrer_id = referrer.id
        await db.commit()

    return {"status": "success"}
