from fastapi import APIRouter, Request, HTTPException, status, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from app.services.notifications import send_order_notification
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Order, MooGoldFulfillment, Transaction
from app.services.refunds import refund_order_to_balance
from app.core.config import settings
import hmac
import hashlib

router = APIRouter()


class MooGoldWebhookPayload(BaseModel):
    status: str = Field(..., description="Order status from MooGold")
    message: str = Field(default="")
    order_id: int = Field(..., gt=0, description="MooGold order ID")
    total: str = Field(default="0.00")
    account_details: Optional[Dict[str, Any]] = Field(default=None)


def verify_moogold_webhook_signature(
    payload_body: bytes,
    signature: str,
    secret_key: str
) -> bool:
    """Verify MooGold webhook HMAC signature."""
    expected = hmac.new(
        secret_key.encode(),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/moogold")
async def moogold_callback(
    request: Request,
    x_signature: str = Header(..., alias="X-Signature"),
    db: AsyncSession = Depends(get_db)
):
    """Handle MooGold order status callbacks."""
    # Read raw body for signature verification
    payload_body = await request.body()
    
    # Verify signature
    if not verify_moogold_webhook_signature(payload_body, x_signature, settings.MOOGOLD_SECRET_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    try:
        payload_raw = await request.json()
        payload = MooGoldWebhookPayload(**payload_raw)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {str(e)}"
        )

    # Map MooGold order to local fulfillment using moogold_order_id.
    # A local order may create multiple MooGold orders, so this table is safer
    # than storing only one id in orders.moogold_order_id.
    result = await db.execute(
        select(MooGoldFulfillment).where(MooGoldFulfillment.moogold_order_id == str(payload.order_id))
    )
    fulfillment = result.scalar_one_or_none()

    order = None
    if fulfillment:
        result = await db.execute(select(Order).where(Order.id == fulfillment.order_id))
        order = result.scalar_one_or_none()
    else:
        # Backward compatibility for one-item old orders.
        result = await db.execute(
            select(Order).where(Order.moogold_order_id == str(payload.order_id))
        )
        order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with MooGold ID {payload.order_id} not found"
        )

    # Map MooGold status to local status.
    status_mapping = {
        "completed": "completed",
        "refunded": "refunded",
        "incorrect-details": "cancelled",
        "processing": "processing",
    }
    local_status = status_mapping.get(payload.status)
    if local_status not in {"completed", "refunded", "cancelled", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MooGold status received"
        )

    if fulfillment:
        fulfillment.status = local_status
        fulfillment.response_payload = str(payload_raw)[:4000]
        fulfillment.updated_at = datetime.utcnow()

    # If the order has multiple MooGold fulfillments, complete the local order
    # only after all MooGold parts are completed.
    result = await db.execute(
        select(MooGoldFulfillment).where(MooGoldFulfillment.order_id == order.id)
    )
    fulfillments = result.scalars().all()
    statuses = {f.status for f in fulfillments} if fulfillments else {local_status}

    if statuses and statuses.issubset({"completed"}):
        order.status = "completed"
        # Create one completion transaction only.
        existing_tx = await db.execute(
            select(Transaction).where(
                Transaction.order_id == order.id,
                Transaction.type == "withdrawal",
                Transaction.status == "completed",
            )
        )
        if existing_tx.scalar_one_or_none() is None:
            db.add(Transaction(
                user_id=order.user_id,
                order_id=order.id,
                type="withdrawal",
                amount=order.total_amount,
                currency=order.currency,
                status="completed",
                description=f"Order #{order.order_number} completed via MooGold webhook",
            ))
    elif statuses.issubset({"refunded", "cancelled"}):
        order.status = "refunded" if "refunded" in statuses else "cancelled"
    else:
        order.status = "processing"

    if payload.account_details:
        # Store a short copy for admin/user visibility. Full response is kept in fulfillment.response_payload.
        details_str = str(payload.account_details)
        order.payment_receipt = details_str[:1000]

    order.updated_at = datetime.utcnow()
    if order.status == "refunded":
        await db.run_sync(lambda sync_session: refund_order_to_balance(sync_session, order.id, payload.message or payload.status, notify=True))

    await db.commit()

    # Notify user/admin
    send_order_notification.delay(order.id, order.status)

    return {"status": "success", "received": True, "order_id": order.id, "local_status": order.status}
