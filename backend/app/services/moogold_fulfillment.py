import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import joinedload, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(SYNC_DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine)


class MooGoldFulfillmentError(Exception):
    pass


def _now():
    return datetime.utcnow()


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _extract_moogold_order_id(response: dict) -> Optional[str]:
    """MooGold responses can contain order id in different shapes."""
    if not isinstance(response, dict):
        return None
    candidates = [
        response.get("order_id"),
        response.get("id"),
        response.get("orderId"),
        (response.get("account_details") or {}).get("order_id") if isinstance(response.get("account_details"), dict) else None,
        (response.get("data") or {}).get("order_id") if isinstance(response.get("data"), dict) else None,
    ]
    for value in candidates:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _generate_auth(payload: dict, path: str) -> tuple[int, str]:
    timestamp = int(time.time())
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    string_to_sign = f"{payload_str}{timestamp}{path}"
    signature = hmac.new(
        settings.MOOGOLD_SECRET_KEY.encode(),
        string_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()
    return timestamp, signature


def _basic_auth() -> str:
    credentials = f"{settings.MOOGOLD_PARTNER_ID}:{settings.MOOGOLD_SECRET_KEY}"
    return base64.b64encode(credentials.encode()).decode()


def moogold_request(path: str, data: Optional[dict] = None) -> dict:
    if settings.MOOGOLD_TEST_MODE:
        # Safe dry-run mode: never sends money/order requests to MooGold.
        # This lets the full local chain be tested on VPS without buying stock.
        fake_id_source = (data or {}).get("partnerOrderId") or (data or {}).get("partner_order_id") or int(time.time())
        return {
            "status": True,
            "message": "MOOGOLD_TEST_MODE: fake response, no real order was created",
            "order_id": f"TEST-{fake_id_source}",
            "data": {"path": path, "test_mode": True},
        }

    if not settings.MOOGOLD_PARTNER_ID or not settings.MOOGOLD_SECRET_KEY:
        raise MooGoldFulfillmentError("MooGold credentials are not configured")

    url = f"{settings.MOOGOLD_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    payload = {"path": path, **(data or {})}
    timestamp, signature = _generate_auth(payload, path)
    headers = {
        "Authorization": f"Basic {_basic_auth()}",
        "auth": signature,
        "timestamp": str(timestamp),
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=45.0) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def create_moogold_order(
    *,
    category: int,
    product_id: int,
    quantity: int,
    user_id: str,
    server: Optional[str],
    partner_order_id: str,
) -> dict:
    data = {
        "data": {
            "category": category,
            "product-id": product_id,
            "quantity": quantity,
            "User ID": user_id,
        },
        "partnerOrderId": partner_order_id,
    }
    if server:
        data["data"]["Server"] = server
    return moogold_request("order/create_order", data)


def _get_moogold_category(product) -> int:
    """Return 1=Direct Top Up or 2=eVouchers.

    The local Category.moogold_id may be used for MooGold product listing IDs in some
    projects, so we only trust it as order category if it is 1 or 2. Otherwise we use
    MOOGOLD_DEFAULT_ORDER_CATEGORY.
    """
    try:
        cat_value = int(getattr(getattr(product, "category", None), "moogold_id", 0) or 0)
        if cat_value in (1, 2):
            return cat_value
    except Exception:
        pass
    return int(settings.MOOGOLD_DEFAULT_ORDER_CATEGORY or 1)


def _ensure_completion_transaction(db, order):
    from app.models.models import Transaction

    existing = db.execute(
        select(Transaction).where(
            Transaction.order_id == order.id,
            Transaction.type == "withdrawal",
            Transaction.status == "completed",
        )
    ).scalar_one_or_none()
    if existing:
        return

    db.add(Transaction(
        user_id=order.user_id,
        order_id=order.id,
        type="withdrawal",
        amount=order.total_amount,
        currency=order.currency,
        status="completed",
        description=f"Order #{order.order_number} completed via MooGold",
    ))


def update_local_order_status_from_fulfillments(db, order_id: int) -> str:
    from app.models.models import MooGoldFulfillment, Order

    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        return "missing"

    fulfillments = db.execute(
        select(MooGoldFulfillment).where(MooGoldFulfillment.order_id == order_id)
    ).scalars().all()
    if not fulfillments:
        return order.status

    statuses = {f.status for f in fulfillments}
    if statuses and statuses.issubset({"completed"}):
        order.status = "completed"
        _ensure_completion_transaction(db, order)
    elif "refunded" in statuses and statuses.issubset({"refunded", "cancelled"}):
        order.status = "refunded"
    elif "cancelled" in statuses and statuses.issubset({"cancelled"}):
        order.status = "cancelled"
    elif "failed" in statuses and not statuses.intersection({"processing", "completed"}):
        # Keep money-safe state: payment received, but fulfillment needs admin attention.
        order.status = "paid"
    else:
        order.status = "processing"
    order.updated_at = _now()
    return order.status


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fulfill_order_via_moogold(self, order_id: int) -> dict:
    """Create MooGold order(s) after a local order is paid.

    Idempotent: if fulfillments already exist, it will not create duplicates.
    Safe failure mode: if MooGold fails, local order stays paid and admin is notified.
    """
    from app.models.models import MooGoldFulfillment, Order, OrderItem
    from app.services.notifications import send_order_notification

    if not settings.MOOGOLD_AUTO_FULFILL_ENABLED:
        return {"status": "skipped", "reason": "MOOGOLD_AUTO_FULFILL_ENABLED=false", "order_id": order_id}

    with SyncSessionLocal() as db:
        from app.models.models import Product, ProductVariation

        order = db.execute(
            select(Order)
            .options(
                joinedload(Order.items)
                .joinedload(OrderItem.variation)
                .joinedload(ProductVariation.product)
                .joinedload(Product.category)
            )
            .where(Order.id == order_id)
        ).unique().scalar_one_or_none()
        if not order:
            return {"status": "not_found", "order_id": order_id}

        if order.status not in {"paid", "processing"}:
            return {"status": "skipped", "reason": f"order_status={order.status}", "order_id": order_id}

        result_summary = []
        created_any = False
        failed_any = False

        for item in order.items:
            variation = item.variation
            product = variation.product
            partner_order_id = f"{order.partner_order_id or order.order_number}-{item.id}"

            existing = db.execute(
                select(MooGoldFulfillment).where(MooGoldFulfillment.partner_order_id == partner_order_id)
            ).scalar_one_or_none()
            if existing and (existing.status == "completed" or (existing.status == "processing" and existing.moogold_order_id)):
                result_summary.append({"item_id": item.id, "status": "exists", "fulfillment_id": existing.id})
                continue

            fulfillment = existing or MooGoldFulfillment(
                order_id=order.id,
                order_item_id=item.id,
                partner_order_id=partner_order_id,
                status="queued",
            )
            if not existing:
                db.add(fulfillment)
                db.flush()

            fulfillment.attempts = (fulfillment.attempts or 0) + 1
            fulfillment.updated_at = _now()

            moogold_variation_id = getattr(variation, "moogold_variation_id", None)
            if not moogold_variation_id:
                fulfillment.status = "failed"
                fulfillment.error_message = "Product variation has no moogold_variation_id"
                failed_any = True
                result_summary.append({"item_id": item.id, "status": "failed", "reason": fulfillment.error_message})
                continue

            payload_preview = {
                "category": _get_moogold_category(product),
                "product_id": int(moogold_variation_id),
                "quantity": int(item.quantity),
                "user_id": order.target_id,
                "server": order.target_server,
                "partner_order_id": partner_order_id,
            }
            fulfillment.request_payload = _json_dump(payload_preview)

            try:
                response = create_moogold_order(**payload_preview)
                fulfillment.response_payload = _json_dump(response)

                if isinstance(response, dict) and response.get("status") is False:
                    raise MooGoldFulfillmentError(response.get("message") or "MooGold returned status=false")

                moogold_order_id = _extract_moogold_order_id(response)
                if moogold_order_id:
                    fulfillment.moogold_order_id = moogold_order_id
                fulfillment.status = "processing"
                fulfillment.error_message = None
                created_any = True
                result_summary.append({"item_id": item.id, "status": "processing", "moogold_order_id": moogold_order_id})
            except Exception as exc:
                fulfillment.status = "failed"
                fulfillment.error_message = str(exc)[:2000]
                failed_any = True
                logger.exception("MooGold fulfillment failed for local order %s item %s", order.id, item.id)
                result_summary.append({"item_id": item.id, "status": "failed", "reason": str(exc)})

        if created_any:
            order.status = "processing"
            order.updated_at = _now()
            # Keep old single-id field useful for simple/one-item orders.
            ids = db.execute(
                select(MooGoldFulfillment.moogold_order_id).where(
                    MooGoldFulfillment.order_id == order.id,
                    MooGoldFulfillment.moogold_order_id != None,
                )
            ).scalars().all()
            if ids:
                order.moogold_order_id = ",".join(str(x) for x in ids if x)

        if failed_any and not created_any:
            # Payment is received, but fulfillment is not sent. Admin must fix mapping/credentials.
            order.status = "paid"
            order.updated_at = _now()

        db.commit()

    if created_any:
        send_order_notification.delay(order_id, "processing")
    if failed_any:
        send_order_notification.delay(order_id, "moogold_failed")

    return {"status": "ok", "order_id": order_id, "created_any": created_any, "failed_any": failed_any, "items": result_summary}
