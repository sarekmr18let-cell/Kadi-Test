import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import select

logger = logging.getLogger(__name__)

FINAL_UNSUCCESSFUL_STATUSES = {"refunded", "failed", "cancelled"}
COMPLETED_STATUSES = {"completed"}
REFUNDABLE_PROVIDER_ERRORS = {
    "wrong_price",
    "offer_not_found",
    "product_offer_group_not_found",
    "provider error",
    "provider_error",
}


@dataclass
class RefundResult:
    status: str
    order_id: int
    amount: float = 0.0
    reason: str | None = None
    transaction_id: int | None = None


def _normalize(value) -> str:
    return str(value or "").strip().lower()


def _has_completed_refund(db, Transaction, order_id: int) -> bool:
    existing = db.execute(
        select(Transaction).where(
            Transaction.order_id == order_id,
            Transaction.type == "refund",
            Transaction.status == "completed",
        )
    ).scalar_one_or_none()
    return existing is not None


def _safe_to_refund_order(order, fulfillments: Iterable) -> tuple[bool, str]:
    statuses = {_normalize(getattr(f, "status", None)) for f in fulfillments}
    statuses.discard("")

    if statuses:
        if statuses.intersection(COMPLETED_STATUSES):
            return False, "partial_provider_success_needs_review"
        if statuses.issubset(FINAL_UNSUCCESSFUL_STATUSES):
            return True, "all_fulfillments_final_unsuccessful"
        return False, "fulfillments_not_final"

    order_status = _normalize(getattr(order, "status", None))
    provider_status = _normalize(getattr(order, "provider_status", None))
    response_text = _normalize(getattr(order, "provider_response", None))

    if order_status == "refunded" or provider_status == "refunded":
        return True, "order_refunded_status"
    if order_status == "failed" or provider_status == "failed":
        if any(token in response_text for token in REFUNDABLE_PROVIDER_ERRORS):
            return True, "final_provider_failed_status"
        return False, "failed_status_requires_review"
    return False, "order_not_refundable"


def _mark_needs_review(order, reason: str) -> None:
    order.provider_status = "needs_review"
    response = order.provider_response if isinstance(order.provider_response, dict) else {}
    order.provider_response = {**response, "refund_review_reason": reason}
    order.updated_at = datetime.utcnow()


def refund_order_to_balance(db, order_id: int, reason: str) -> RefundResult:
    """Idempotently return a fully failed/refunded provider order to Kadi balance."""
    from app.models.models import MooGoldFulfillment, Order, Transaction, User

    order = db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    ).scalar_one_or_none()
    if not order:
        return RefundResult(status="not_found", order_id=order_id, reason=reason)

    user = db.execute(
        select(User).where(User.id == order.user_id).with_for_update()
    ).scalar_one_or_none()
    if not user:
        return RefundResult(status="user_not_found", order_id=order_id, reason=reason)

    if _has_completed_refund(db, Transaction, order.id):
        return RefundResult(status="already_refunded", order_id=order.id, amount=float(order.total_amount or 0), reason=reason)

    fulfillments = db.execute(
        select(MooGoldFulfillment)
        .where(MooGoldFulfillment.order_id == order.id)
        .with_for_update()
    ).scalars().all()

    safe, safety_reason = _safe_to_refund_order(order, fulfillments)
    if not safe:
        if safety_reason == "partial_provider_success_needs_review":
            _mark_needs_review(order, safety_reason)
            db.flush()
        return RefundResult(status=safety_reason, order_id=order.id, reason=reason)

    amount = float(order.total_amount or 0)
    user.balance = float(user.balance or 0) + amount
    order.status = "refunded"
    order.provider_status = "refunded"
    order.updated_at = datetime.utcnow()

    tx = Transaction(
        user_id=order.user_id,
        order_id=order.id,
        type="refund",
        amount=amount,
        currency="UZS",
        status="completed",
        description=f"Auto refund for provider refunded order #{order.id}: {reason}",
    )
    db.add(tx)
    db.flush()

    return RefundResult(status="refunded", order_id=order.id, amount=amount, reason=reason, transaction_id=tx.id)
