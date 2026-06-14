import hashlib
import json
import random
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.models import (
    User,
    Order,
    PromoCode,
    Transaction,
    P2PCard,
    P2PPaymentSession,
    P2PIncomingPayment,
    BalanceTopUp,
)
from app.services.notifications import send_order_notification

PAYMENT_TTL_MINUTES = int(settings.P2P_PAYMENT_TTL_MINUTES or 5)
UNIQUE_AMOUNT_MIN = 1
UNIQUE_AMOUNT_MAX = 499


_AMOUNT_PATTERNS = [
    # Incoming transaction line from HUMO/CardXabar style bots:
    # ➕ 440.000,00 UZS / + 440,000.00 UZS / ➕ 21 736.00 UZS
    re.compile(r"(?:➕|\+)\s*([0-9][0-9\s\u00a0,\.]*?)\s*(?:UZS|сум|sum|so['`]?m)", re.IGNORECASE),
]

_INCOME_KEYWORDS = ("пополнение", "kirim", "tushum", "income", "credit")
_OUTGOING_KEYWORDS = ("оплата", "операция", "списание", "chiqim", "payment", "debit")
_CARD_LAST4_PATTERNS = [
    re.compile(r"(?:HUMOCARD|UZCARD|CARD|КАРТ[АЫ]?|💳)[^0-9*]{0,20}\*+\s*(\d{4})", re.IGNORECASE),
    re.compile(r"\*{2,}\s*(\d{4})"),
]
_TIME_PATTERN = re.compile(r"(\d{1,2}:\d{2})\s+(\d{2}\.\d{2}\.\d{4})")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def clean_card_number(card_number: str) -> str:
    return "".join(ch for ch in card_number if ch.isdigit())


def card_last4(card_number: str) -> str:
    cleaned = clean_card_number(card_number)
    return cleaned[-4:]


def is_income_notification(text: str) -> bool:
    """Return True only for incoming card top-up notifications.

    HUMO example that must match:
        🎉 Пополнение
        ➕ 440.000,00 UZS

    Expense examples that must NOT match:
        💸 Оплата / ➖ ...
        💸 Операция / ➖ ...
    """
    normalized = (text or "").lower()
    if any(keyword in normalized for keyword in _OUTGOING_KEYWORDS) or "➖" in normalized:
        return False
    if any(keyword in normalized for keyword in _INCOME_KEYWORDS) or "➕" in normalized:
        return True
    return False


def normalize_money_amount(raw: str) -> Optional[float]:
    """Parse UZS amount written in US, RU/UZ or spaced formats.

    Supported examples:
    - 440.000,00 -> 440000.00
    - 440,000.00 -> 440000.00
    - 21 736.00  -> 21736.00
    - 19000      -> 19000.00
    """
    if not raw:
        return None

    value = raw.strip().replace(" ", "").replace("\u00a0", "")
    if not value:
        return None

    last_dot = value.rfind(".")
    last_comma = value.rfind(",")

    if last_dot != -1 and last_comma != -1:
        # Decimal separator is whichever appears last.
        if last_comma > last_dot:
            # 440.000,00
            normalized = value.replace(".", "").replace(",", ".")
        else:
            # 440,000.00
            normalized = value.replace(",", "")
    elif last_comma != -1:
        # 19000,00 means decimal comma. 19,000 means thousands.
        decimals = len(value) - last_comma - 1
        if decimals == 2:
            normalized = value.replace(".", "").replace(",", ".")
        else:
            normalized = value.replace(",", "")
    elif last_dot != -1:
        # 440.000 is usually thousands in UZ/RU formats, but 440.00 is decimal.
        parts = value.split(".")
        if len(parts) > 2:
            # 1.234.567 or 1.234.567.89; keep decimal only if last group has 2 digits.
            if len(parts[-1]) == 2:
                normalized = "".join(parts[:-1]) + "." + parts[-1]
            else:
                normalized = "".join(parts)
        else:
            decimals = len(value) - last_dot - 1
            if decimals == 3:
                normalized = value.replace(".", "")
            else:
                normalized = value
    else:
        normalized = value

    try:
        return round(float(normalized), 2)
    except ValueError:
        return None


def parse_money_amount(text: str) -> Optional[float]:
    if not is_income_notification(text):
        return None

    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(text or "")
        if not match:
            continue
        parsed = normalize_money_amount(match.group(1))
        if parsed is not None:
            return parsed
    return None


def parse_card_last4(text: str) -> Optional[str]:
    for pattern in _CARD_LAST4_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(1)
    return None


def parse_payment_datetime(text: str) -> Optional[datetime]:
    match = _TIME_PATTERN.search(text or "")
    if not match:
        return None
    time_part, date_part = match.groups()
    try:
        dt = datetime.strptime(f"{date_part} {time_part}", "%d.%m.%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def make_external_id(raw_text: str, source: str) -> str:
    digest = hashlib.sha256(f"{source}:{raw_text}".encode("utf-8")).hexdigest()
    return digest[:64]


async def expire_old_p2p_sessions(db: AsyncSession) -> int:
    result = await db.execute(
        select(P2PPaymentSession).where(
            P2PPaymentSession.status == "active",
            P2PPaymentSession.expires_at < _now(),
        )
    )
    expired = result.scalars().all()
    for session in expired:
        session.status = "expired"
        session.updated_at = _now()
    if expired:
        await db.flush()
    return len(expired)


async def expire_old_balance_topups(db: AsyncSession) -> int:
    result = await db.execute(
        select(BalanceTopUp).where(
            BalanceTopUp.status == "pending",
            BalanceTopUp.expires_at < _now(),
        )
    )
    expired = result.scalars().all()
    for topup in expired:
        topup.status = "expired"
        topup.updated_at = _now()
        topup.note = (topup.note or "") + "\nExpired automatically."
    if expired:
        await db.flush()
    return len(expired)


async def get_active_session_for_order(db: AsyncSession, order_id: int) -> Optional[P2PPaymentSession]:
    await expire_old_p2p_sessions(db)
    result = await db.execute(
        select(P2PPaymentSession)
        .options(selectinload(P2PPaymentSession.card))
        .where(
            P2PPaymentSession.order_id == order_id,
            P2PPaymentSession.status == "active",
            P2PPaymentSession.expires_at >= _now(),
        )
        .order_by(P2PPaymentSession.created_at.desc())
    )
    return result.scalar_one_or_none()


async def get_active_topup_for_user(db: AsyncSession, user_id: int) -> Optional[BalanceTopUp]:
    await expire_old_balance_topups(db)
    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(
            BalanceTopUp.user_id == user_id,
            BalanceTopUp.status == "pending",
            BalanceTopUp.expires_at >= _now(),
        )
        .order_by(BalanceTopUp.created_at.desc())
    )
    return result.scalar_one_or_none()


async def pick_free_card(db: AsyncSession, amount: float) -> P2PCard:
    """Pick a card that has no active order session and no active balance top-up.

    Business rule: one card = one active payment window. This lets us match by
    card + amount + time without forcing unique amounts.
    """
    await expire_old_p2p_sessions(db)
    await expire_old_balance_topups(db)

    active_order_cards = (
        select(P2PPaymentSession.card_id)
        .where(
            P2PPaymentSession.status == "active",
            P2PPaymentSession.expires_at >= _now(),
        )
        .subquery()
    )
    active_topup_cards = (
        select(BalanceTopUp.card_id)
        .where(
            BalanceTopUp.status == "pending",
            BalanceTopUp.expires_at >= _now(),
        )
        .subquery()
    )

    query = (
        select(P2PCard)
        .where(
            P2PCard.is_active == True,
            P2PCard.min_amount <= amount,
            or_(P2PCard.max_amount == None, P2PCard.max_amount >= amount),
            P2PCard.id.not_in(select(active_order_cards.c.card_id)),
            P2PCard.id.not_in(select(active_topup_cards.c.card_id)),
        )
        .order_by(P2PCard.sort_order, P2PCard.id)
    )
    result = await db.execute(query)
    card = result.scalars().first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No free P2P card is available for this amount. Add more cards or wait until a payment window expires.",
        )
    return card


async def generate_unique_amount(db: AsyncSession, base_amount: float) -> tuple[float, float]:
    # Kept for backward compatibility with the old order-payment flow.
    base = round(float(base_amount), 2)
    for _ in range(60):
        suffix = random.randint(UNIQUE_AMOUNT_MIN, UNIQUE_AMOUNT_MAX)
        assigned = round(base + suffix, 2)
        result = await db.execute(
            select(P2PPaymentSession.id).where(
                P2PPaymentSession.status == "active",
                P2PPaymentSession.expires_at >= _now(),
                P2PPaymentSession.assigned_amount == assigned,
            )
        )
        if result.scalar_one_or_none() is None:
            return assigned, float(suffix)
    raise HTTPException(status_code=409, detail="Could not generate unique payment amount. Try again.")


async def create_or_get_payment_session(db: AsyncSession, order: Order) -> P2PPaymentSession:
    """Legacy direct order P2P session. Kept so old orders are not broken."""
    if order.status not in {"awaiting_payment", "payment_submitted"}:
        raise HTTPException(status_code=400, detail=f"Order status does not allow payment: {order.status}")

    existing = await get_active_session_for_order(db, order.id)
    if existing:
        return existing

    card = await pick_free_card(db, order.total_amount)
    assigned_amount, unique_amount = await generate_unique_amount(db, order.total_amount)
    session = P2PPaymentSession(
        order_id=order.id,
        card_id=card.id,
        base_amount=order.total_amount,
        unique_amount=unique_amount,
        assigned_amount=assigned_amount,
        status="active",
        expires_at=_now() + timedelta(minutes=PAYMENT_TTL_MINUTES),
    )
    db.add(session)
    await db.flush()

    result = await db.execute(
        select(P2PPaymentSession)
        .options(selectinload(P2PPaymentSession.card))
        .where(P2PPaymentSession.id == session.id)
    )
    return result.scalar_one()


async def create_balance_topup(db: AsyncSession, user_id: int, amount: float) -> BalanceTopUp:
    amount = round(float(amount), 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Top-up amount must be greater than 0")
    if amount < float(settings.WALLET_TOPUP_MIN_AMOUNT or 0):
        raise HTTPException(status_code=400, detail=f"Minimum top-up amount is {settings.WALLET_TOPUP_MIN_AMOUNT} UZS")
    if settings.WALLET_TOPUP_MAX_AMOUNT and amount > float(settings.WALLET_TOPUP_MAX_AMOUNT):
        raise HTTPException(status_code=400, detail=f"Maximum top-up amount is {settings.WALLET_TOPUP_MAX_AMOUNT} UZS")

    existing = await get_active_topup_for_user(db, user_id)
    if existing:
        if abs(existing.amount - amount) <= 0.01:
            return existing
        raise HTTPException(
            status_code=409,
            detail="You already have an active top-up. Pay it, cancel it, or wait until it expires before creating a new one.",
        )

    card = await pick_free_card(db, amount)
    topup = BalanceTopUp(
        user_id=user_id,
        card_id=card.id,
        amount=amount,
        currency="UZS",
        status="pending",
        expires_at=_now() + timedelta(minutes=PAYMENT_TTL_MINUTES),
    )
    db.add(topup)
    await db.flush()

    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(BalanceTopUp.id == topup.id)
    )
    return result.scalar_one()


async def count_promo_usage_if_needed(db: AsyncSession, order: Order) -> None:
    if not order.promo_code or order.promo_usage_counted:
        return
    result = await db.execute(
        select(PromoCode).where(
            PromoCode.code == order.promo_code.upper(),
            PromoCode.is_active == True,
        )
    )
    promo = result.scalar_one_or_none()
    if not promo:
        return
    if promo.usage_limit and promo.usage_count >= promo.usage_limit:
        raise HTTPException(status_code=400, detail="Promo code usage limit reached")
    promo.usage_count += 1
    order.promo_usage_counted = True


async def credit_balance_topup(
    db: AsyncSession,
    topup: BalanceTopUp,
    incoming: Optional[P2PIncomingPayment] = None,
    note: Optional[str] = None,
) -> None:
    if topup.status == "paid":
        if incoming:
            incoming.status = "duplicate"
        return

    result = await db.execute(select(User).where(User.id == topup.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Top-up user not found")

    user.balance = round(float(user.balance or 0) + float(topup.amount), 2)
    topup.status = "paid"
    topup.paid_at = incoming.paid_at if incoming else _now()
    topup.updated_at = _now()
    if incoming:
        topup.incoming_payment_id = incoming.id
        topup.note = ((topup.note or "") + "\n" + (incoming.raw_text or "")[:1000]).strip()
        incoming.status = "matched"
        incoming.matched_topup_id = topup.id
        incoming.matched_user_id = topup.user_id
    if note:
        topup.note = ((topup.note or "") + "\n" + note).strip()

    tx = Transaction(
        user_id=topup.user_id,
        order_id=None,
        type="topup",
        amount=topup.amount,
        currency=topup.currency,
        status="completed",
        description=f"Balance top-up #{topup.id}",
    )
    db.add(tx)


async def mark_order_paid_by_session(
    db: AsyncSession,
    order: Order,
    session: P2PPaymentSession,
    incoming: P2PIncomingPayment,
) -> None:
    """Legacy direct order payment matcher. Kept for backward compatibility."""
    if order.status in {"completed", "processing", "paid"}:
        incoming.status = "duplicate"
        return

    order.status = "paid"
    order.payment_method = "p2p_auto"
    order.payment_amount = incoming.amount or session.assigned_amount
    order.payment_receipt = (incoming.raw_text or "")[:500]
    order.paid_at = incoming.paid_at or _now()
    order.updated_at = _now()

    session.status = "paid"
    session.paid_at = order.paid_at
    session.incoming_payment_id = incoming.id
    session.updated_at = _now()

    incoming.status = "matched"
    incoming.matched_order_id = order.id
    incoming.matched_session_id = session.id

    await count_promo_usage_if_needed(db, order)


def parse_incoming_payment_payload(raw_text: str, source: str, amount: Optional[float], card_last4_value: Optional[str]) -> dict:
    is_income = is_income_notification(raw_text)
    parsed = {
        "is_income": is_income,
        "amount": amount if amount is not None else parse_money_amount(raw_text),
        "card_last4": card_last4_value or parse_card_last4(raw_text),
        "paid_at": parse_payment_datetime(raw_text),
    }
    parsed["parser"] = "p2p_v6_humo_wallet_card_lock"
    parsed["source"] = source
    return parsed


async def _match_balance_topup_first(
    db: AsyncSession,
    incoming: P2PIncomingPayment,
    amount: float,
    card_last4_value: Optional[str],
) -> bool:
    """Try wallet top-up matching before legacy direct order matching.

    Since a card is locked to only one active top-up, card + amount + time is
    enough for safe automatic balance crediting. Wrong amount or late payment is
    intentionally sent to needs_review instead of being credited blindly.
    """
    if not card_last4_value:
        incoming.status = "error"
        return True

    await expire_old_balance_topups(db)

    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .join(P2PCard, BalanceTopUp.card_id == P2PCard.id)
        .where(
            BalanceTopUp.status == "pending",
            BalanceTopUp.expires_at >= _now(),
            P2PCard.last4 == card_last4_value,
        )
        .order_by(BalanceTopUp.created_at.asc())
    )
    active_topup = result.scalar_one_or_none()
    if active_topup:
        incoming.matched_topup_id = active_topup.id
        incoming.matched_user_id = active_topup.user_id
        if abs(round(float(amount), 2) - round(float(active_topup.amount), 2)) <= 0.01:
            await credit_balance_topup(db, active_topup, incoming)
        else:
            incoming.status = "needs_review"
            active_topup.status = "needs_review"
            active_topup.note = (
                f"Amount mismatch. Expected {active_topup.amount} UZS, got {amount} UZS.\n"
                f"Raw: {(incoming.raw_text or '')[:1000]}"
            )
            active_topup.updated_at = _now()
        return True

    # Late payment: expired top-up for same card and same amount in the last 24h.
    late_cutoff = _now() - timedelta(hours=24)
    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .join(P2PCard, BalanceTopUp.card_id == P2PCard.id)
        .where(
            BalanceTopUp.status.in_(["expired", "needs_review"]),
            BalanceTopUp.expires_at >= late_cutoff,
            P2PCard.last4 == card_last4_value,
        )
        .order_by(BalanceTopUp.expires_at.desc())
    )
    expired_candidates = result.scalars().all()
    for topup in expired_candidates:
        if abs(round(float(amount), 2) - round(float(topup.amount), 2)) <= 0.01:
            incoming.status = "needs_review"
            incoming.matched_topup_id = topup.id
            incoming.matched_user_id = topup.user_id
            topup.status = "needs_review"
            topup.note = (
                f"Payment arrived after expiry. Expected {topup.amount} UZS, got {amount} UZS.\n"
                f"Raw: {(incoming.raw_text or '')[:1000]}"
            )
            topup.updated_at = _now()
            return True

    return False


async def process_incoming_p2p_payment(
    db: AsyncSession,
    source: str,
    raw_text: str,
    amount: Optional[float] = None,
    card_last4_value: Optional[str] = None,
    external_id: Optional[str] = None,
) -> P2PIncomingPayment:
    parsed = parse_incoming_payment_payload(raw_text, source, amount, card_last4_value)
    final_amount = parsed["amount"]
    final_last4 = parsed["card_last4"]
    final_external_id = external_id or make_external_id(raw_text, source)

    # Idempotency: same bank notification should not pay twice.
    result = await db.execute(select(P2PIncomingPayment).where(P2PIncomingPayment.external_id == final_external_id))
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = existing.status or "duplicate"
        return existing

    incoming = P2PIncomingPayment(
        source=source,
        raw_text=raw_text,
        amount=final_amount,
        currency="UZS",
        card_last4=final_last4,
        external_id=final_external_id,
        paid_at=parsed["paid_at"] or _now(),
        status="new",
        parser_data=json.dumps(parsed, ensure_ascii=False, default=str),
    )
    db.add(incoming)
    await db.flush()

    if not parsed.get("is_income"):
        incoming.status = "ignored"
        return incoming

    if final_amount is None:
        incoming.status = "error"
        return incoming

    # New wallet flow: top-up balance first, then purchases are paid from balance.
    matched_wallet = await _match_balance_topup_first(db, incoming, final_amount, final_last4)
    if matched_wallet:
        return incoming

    # Backward compatible fallback for old direct order payment sessions.
    await expire_old_p2p_sessions(db)

    query = (
        select(P2PPaymentSession)
        .options(selectinload(P2PPaymentSession.card), selectinload(P2PPaymentSession.order))
        .where(
            P2PPaymentSession.status == "active",
            P2PPaymentSession.expires_at >= _now(),
            P2PPaymentSession.assigned_amount == round(float(final_amount), 2),
        )
        .order_by(P2PPaymentSession.created_at.asc())
    )
    result = await db.execute(query)
    candidates = result.scalars().all()

    matched_session = None
    for session in candidates:
        if final_last4 and session.card.last4 != final_last4:
            continue
        matched_session = session
        break

    if not matched_session:
        incoming.status = "unmatched"
        return incoming

    await mark_order_paid_by_session(db, matched_session.order, matched_session, incoming)
    send_order_notification.delay(matched_session.order.id, "paid")
    return incoming
