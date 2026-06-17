from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Order, Transaction, OrderItem, ProductVariation
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


@router.get("/operations")
async def get_operations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clean public operation history for Mini App.

    Shows only:
    - topup: balance top-up
    - purchase: purchase from balance

    Hides technical transactions:
    - withdrawal
    """
    result = await db.execute(
        select(Transaction)
        .options(
            selectinload(Transaction.order)
            .selectinload(Order.items)
            .selectinload(OrderItem.variation)
            .selectinload(ProductVariation.product)
        )
        .where(
            Transaction.user_id == int(current_user["sub"]),
            Transaction.type.in_(["topup", "purchase"]),
        )
        .order_by(Transaction.created_at.desc())
        .limit(100)
    )

    operations = []

    for tx in result.scalars().all():
        tx_type = tx.type
        raw_amount = float(tx.amount or 0)
        order = getattr(tx, "order", None)

        product_name = None
        item_names = []
        region = None
        target = None
        nickname = None
        order_number = None

        if order:
            order_number = getattr(order, "order_number", None) or str(getattr(order, "id", ""))
            region = (
                getattr(order, "target_region_label", None)
                or getattr(order, "target_region", None)
            )

            target_id = getattr(order, "target_id", None)
            target_server = getattr(order, "target_server", None)

            if target_id and target_server:
                target = f"{target_id} / {target_server}"
            else:
                target = target_id or target_server

            nickname = getattr(order, "verified_target_name", None)

            for item in getattr(order, "items", []) or []:
                variation = getattr(item, "variation", None)
                if not variation:
                    continue

                if getattr(variation, "name", None):
                    qty = getattr(item, "quantity", 1) or 1
                    try:
                        qty_int = int(qty)
                    except Exception:
                        qty_int = 1

                    if qty_int > 1:
                        item_names.append(f"{variation.name} x{qty_int}")
                    else:
                        item_names.append(variation.name)

                product = getattr(variation, "product", None)
                if product and getattr(product, "name", None) and not product_name:
                    product_name = product.name

        if tx_type == "topup":
            amount = abs(raw_amount)
            title = "Пополнение баланса"
            group = "topup"
            display_amount = f"+{int(amount):,}".replace(",", " ")
        else:
            amount = -abs(raw_amount)
            title = "Покупка"
            group = "purchase"
            display_amount = f"-{int(abs(amount)):,}".replace(",", " ")

        operations.append({
            "id": tx.id,
            "transaction_id": tx.id,
            "order_id": tx.order_id,
            "order_number": order_number,
            "type": tx_type,
            "group": group,
            "title": title,
            "amount": amount,
            "display_amount": display_amount,
            "currency": tx.currency or "UZS",
            "status": tx.status or "completed",
            "description": tx.description,
            "product_name": product_name,
            "item_names": item_names,
            "item_name": item_names[0] if item_names else None,
            "region": region,
            "target": target,
            "nickname": nickname,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        })

    return operations


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
