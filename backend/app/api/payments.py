from fastapi import APIRouter, HTTPException, status, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import PaymentMethod, Order, P2PPaymentSession, BalanceTopUp
from app.schemas.schemas import (
    PaymentMethodResponse,
    P2PPaymentSessionResponse,
    P2PIncomingPaymentCreate,
    P2PIncomingPaymentResponse,
    BalanceTopUpCreate,
    BalanceTopUpResponse,
)
from app.services.p2p import (
    create_or_get_payment_session,
    process_incoming_p2p_payment,
    create_balance_topup,
    expire_old_balance_topups,
)
from app.services.moogold_fulfillment import fulfill_order_via_moogold

router = APIRouter()


@router.get("/methods", response_model=List[PaymentMethodResponse])
async def list_payment_methods(db: AsyncSession = Depends(get_db)):
    """Get active payment methods (P2P details)."""
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.is_active == True)
        .order_by(PaymentMethod.sort_order)
    )
    methods = result.scalars().all()
    return methods


@router.get("/methods/{method_id}", response_model=PaymentMethodResponse)
async def get_payment_method(method_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PaymentMethod).where(PaymentMethod.id == method_id, PaymentMethod.is_active == True)
    )
    method = result.scalar_one_or_none()
    if not method:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    return method


# ===== Wallet Top-up Flow =====
@router.post("/topups", response_model=BalanceTopUpResponse)
async def create_wallet_topup(
    payload: BalanceTopUpCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a balance top-up and lock one free card for this user.

    Business rule: one card can have only one active payment window. No unique
    amount is required because matching is done by card + amount + time.
    """
    topup = await create_balance_topup(db, int(current_user["sub"]), payload.amount)
    await db.commit()

    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(BalanceTopUp.id == topup.id)
    )
    return result.scalar_one()


@router.get("/topups/active", response_model=BalanceTopUpResponse)
async def get_active_wallet_topup(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await expire_old_balance_topups(db)
    await db.commit()

    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(
            BalanceTopUp.user_id == int(current_user["sub"]),
            BalanceTopUp.status == "pending",
        )
        .order_by(BalanceTopUp.created_at.desc())
    )
    topup = result.scalar_one_or_none()
    if not topup:
        raise HTTPException(status_code=404, detail="No active top-up")
    return topup


@router.get("/topups/my", response_model=List[BalanceTopUpResponse])
async def list_my_wallet_topups(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await expire_old_balance_topups(db)
    await db.commit()

    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(BalanceTopUp.user_id == int(current_user["sub"]))
        .order_by(BalanceTopUp.created_at.desc())
        .limit(20)
    )
    return result.scalars().all()


@router.post("/topups/{topup_id}/cancel", response_model=BalanceTopUpResponse)
async def cancel_wallet_topup(
    topup_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(
            BalanceTopUp.id == topup_id,
            BalanceTopUp.user_id == int(current_user["sub"]),
        )
    )
    topup = result.scalar_one_or_none()
    if not topup:
        raise HTTPException(status_code=404, detail="Top-up not found")
    if topup.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot cancel top-up with status {topup.status}")
    topup.status = "cancelled"
    await db.commit()
    await db.refresh(topup)
    return topup


# ===== Legacy direct order P2P flow (kept for old orders/backward compatibility) =====
@router.post("/p2p/session/{order_id}", response_model=P2PPaymentSessionResponse)
async def create_p2p_payment_session(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign a free card and exact unique amount for an old direct order payment."""
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == int(current_user["sub"]),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    session = await create_or_get_payment_session(db, order)
    await db.commit()

    result = await db.execute(
        select(P2PPaymentSession)
        .options(selectinload(P2PPaymentSession.card))
        .where(P2PPaymentSession.id == session.id)
    )
    return result.scalar_one()


@router.get("/p2p/session/{order_id}", response_model=P2PPaymentSessionResponse)
async def get_p2p_payment_session(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current active P2P payment session for user's old direct order."""
    result = await db.execute(
        select(P2PPaymentSession)
        .options(selectinload(P2PPaymentSession.card), selectinload(P2PPaymentSession.order))
        .join(Order, Order.id == P2PPaymentSession.order_id)
        .where(
            P2PPaymentSession.order_id == order_id,
            Order.user_id == int(current_user["sub"]),
            P2PPaymentSession.status == "active",
        )
        .order_by(P2PPaymentSession.created_at.desc())
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Active payment session not found")
    return session


@router.post("/p2p/incoming", response_model=P2PIncomingPaymentResponse)
async def p2p_incoming_webhook(
    payload: P2PIncomingPaymentCreate,
    x_p2p_secret: str = Header(..., alias="X-P2P-Secret"),
    db: AsyncSession = Depends(get_db),
):
    """
    Internal endpoint for a bank-bot/Telegram Business bridge.

    Backend parses amount/card, first tries to credit an active balance top-up,
    and only then falls back to legacy direct order sessions.
    """
    if not settings.P2P_WEBHOOK_SECRET or x_p2p_secret != settings.P2P_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid P2P webhook secret")

    incoming = await process_incoming_p2p_payment(
        db=db,
        source=payload.source,
        raw_text=payload.raw_text,
        amount=payload.amount,
        card_last4_value=payload.card_last4,
        external_id=payload.external_id,
    )
    matched_order_id = incoming.matched_order_id
    incoming_status = incoming.status

    await db.commit()
    await db.refresh(incoming)

    # Legacy order-session fallback may still match an old order directly.
    if incoming_status == "matched" and matched_order_id:
        fulfill_order_via_moogold.delay(matched_order_id)

    return incoming
