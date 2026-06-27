import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

import httpx
from celery import shared_task
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import joinedload, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(SYNC_DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine)


class MooGoldFulfillmentError(Exception):
    pass


class GameDropsFulfillmentError(Exception):
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


def _extract_gamedrops_order_id(response: dict, fallback: str) -> str:
    """GameDrops can return ids in several shapes; transactionId is our stable fallback."""
    if isinstance(response, dict):
        candidates = [
            response.get("orderId"),
            response.get("order_id"),
            response.get("id"),
            response.get("transactionId"),
            (response.get("data") or {}).get("orderId") if isinstance(response.get("data"), dict) else None,
            (response.get("data") or {}).get("order_id") if isinstance(response.get("data"), dict) else None,
            (response.get("data") or {}).get("id") if isinstance(response.get("data"), dict) else None,
            (response.get("data") or {}).get("transactionId") if isinstance(response.get("data"), dict) else None,
        ]
        for value in candidates:
            if value is not None and str(value).strip():
                return str(value).strip()
    return fallback


def _is_gamedrops_provider(value) -> bool:
    return str(value or "").strip().lower() in {"gamedrops", "gamesdrop"}


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


def create_gamedrops_order(
    *,
    offer_id: str,
    price: float,
    transaction_id: str,
    game_user_id: str,
    game_server_id: Optional[str],
) -> dict:
    from app.services.gamedrops import GameDropsClient

    async def _create():
        client = GameDropsClient()
        try:
            return await client.create_order(
                offer_id=offer_id,
                price=price,
                transaction_id=transaction_id,
                game_user_id=game_user_id,
                game_server_id=game_server_id,
            )
        finally:
            await client.close()

    return asyncio.run(_create())


def _get_moogold_category(product) -> int:
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
        description=f"Order #{order.order_number} completed via provider",
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
        order.status = "paid"
    else:
        order.status = "processing"
    order.updated_at = _now()
    return order.status


def _load_order_for_fulfillment(db, order_id: int):
    from app.models.models import Order, OrderItem, Product, ProductVariation

    return db.execute(
        select(Order)
        .options(
            joinedload(Order.items)
            .joinedload(OrderItem.variation)
            .joinedload(ProductVariation.product)
            .joinedload(Product.category)
        )
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()


def _fulfill_order_via_gamedrops(order_id: int) -> dict:
    from app.models.models import MooGoldFulfillment
    from app.services.notifications import send_order_notification

    if not settings.PROVIDER_AUTO_FULFILL_ENABLED:
        return {"status": "skipped", "reason": "PROVIDER_AUTO_FULFILL_ENABLED=false", "order_id": order_id}

    with SyncSessionLocal() as db:
        order = _load_order_for_fulfillment(db, order_id)
        if not order:
            return {"status": "not_found", "order_id": order_id}
        if order.status not in {"paid", "processing"}:
            return {"status": "skipped", "reason": f"order_status={order.status}", "order_id": order_id}

        result_summary = []
        created_any = False
        failed_any = False
        skipped_any = False

        for item in order.items:
            variation = item.variation
            product = variation.product
            provider = getattr(variation, "provider", None) or getattr(product, "provider", None)
            if not _is_gamedrops_provider(provider):
                skipped_any = True
                result_summary.append({"item_id": item.id, "status": "skipped", "reason": f"provider={provider}"})
                continue

            for copy_no in range(1, int(item.quantity or 1) + 1):
                transaction_id = f"{order.partner_order_id or order.order_number}-{item.id}-{copy_no}"
                existing = db.execute(
                    select(MooGoldFulfillment).where(MooGoldFulfillment.partner_order_id == transaction_id)
                ).scalar_one_or_none()
                if existing and (existing.status == "completed" or (existing.status == "processing" and existing.moogold_order_id)):
                    result_summary.append({"item_id": item.id, "status": "exists", "fulfillment_id": existing.id})
                    continue

                fulfillment = existing or MooGoldFulfillment(
                    order_id=order.id,
                    order_item_id=item.id,
                    partner_order_id=transaction_id,
                    status="queued",
                )
                if not existing:
                    db.add(fulfillment)
                    db.flush()

                fulfillment.attempts = (fulfillment.attempts or 0) + 1
                fulfillment.updated_at = _now()

                offer_id = getattr(variation, "provider_variation_id", None)
                provider_price = getattr(variation, "provider_price", None)
                if not offer_id:
                    fulfillment.status = "failed"
                    fulfillment.error_message = "Product variation has no provider_variation_id"
                    failed_any = True
                    result_summary.append({"item_id": item.id, "status": "failed", "reason": fulfillment.error_message})
                    continue
                if provider_price is None:
                    fulfillment.status = "failed"
                    fulfillment.error_message = "Product variation has no provider_price"
                    failed_any = True
                    result_summary.append({"item_id": item.id, "status": "failed", "reason": fulfillment.error_message})
                    continue

                request_payload = {
                    "provider": "gamedrops",
                    "offer_id": str(offer_id),
                    "price": float(provider_price),
                    "transaction_id": transaction_id,
                    "game_user_id": order.target_id,
                    "game_server_id": order.target_server,
                }
                fulfillment.request_payload = _json_dump(request_payload)

                try:
                    response = create_gamedrops_order(
                        offer_id=str(offer_id),
                        price=float(provider_price),
                        transaction_id=transaction_id,
                        game_user_id=order.target_id,
                        game_server_id=order.target_server,
                    )
                    fulfillment.response_payload = _json_dump(response)

                    if isinstance(response, dict) and response.get("status") is False:
                        raise GameDropsFulfillmentError(response.get("message") or "GameDrops returned status=false")

                    provider_order_id = _extract_gamedrops_order_id(response, transaction_id)
                    fulfillment.moogold_order_id = provider_order_id
                    fulfillment.status = "processing"
                    fulfillment.error_message = None
                    created_any = True
                    result_summary.append({
                        "item_id": item.id,
                        "status": "processing",
                        "provider": "gamedrops",
                        "provider_order_id": provider_order_id,
                    })
                except Exception as exc:
                    fulfillment.status = "failed"
                    fulfillment.error_message = str(exc)[:2000]
                    failed_any = True
                    logger.exception("GameDrops fulfillment failed for local order %s item %s", order.id, item.id)
                    result_summary.append({"item_id": item.id, "status": "failed", "reason": str(exc)})

        if created_any:
            order.status = "processing"
            order.provider = "gamedrops"
            order.provider_status = "processing"
            order.provider_response = {"items": result_summary}
            order.updated_at = _now()
            ids = db.execute(
                select(MooGoldFulfillment.moogold_order_id).where(
                    MooGoldFulfillment.order_id == order.id,
                    MooGoldFulfillment.moogold_order_id != None,
                )
            ).scalars().all()
            if ids:
                joined_ids = ",".join(str(x) for x in ids if x)
                order.provider_order_id = joined_ids
                order.moogold_order_id = joined_ids

        if failed_any and not created_any:
            order.status = "paid"
            order.provider = "gamedrops"
            order.provider_status = "failed"
            order.provider_response = {"items": result_summary}
            order.updated_at = _now()

        db.commit()

    if created_any:
        send_order_notification.delay(order_id, "processing")
    if failed_any:
        send_order_notification.delay(order_id, "provider_failed")

    return {
        "status": "ok",
        "provider": "gamedrops",
        "order_id": order_id,
        "created_any": created_any,
        "failed_any": failed_any,
        "skipped_any": skipped_any,
        "items": result_summary,
    }


def _fulfill_order_via_moogold(order_id: int) -> dict:
    from app.models.models import MooGoldFulfillment
    from app.services.notifications import send_order_notification

    if not settings.MOOGOLD_AUTO_FULFILL_ENABLED:
        return {"status": "skipped", "reason": "MOOGOLD_AUTO_FULFILL_ENABLED=false", "order_id": order_id}

    with SyncSessionLocal() as db:
        order = _load_order_for_fulfillment(db, order_id)
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
            ids = db.execute(
                select(MooGoldFulfillment.moogold_order_id).where(
                    MooGoldFulfillment.order_id == order.id,
                    MooGoldFulfillment.moogold_order_id != None,
                )
            ).scalars().all()
            if ids:
                order.moogold_order_id = ",".join(str(x) for x in ids if x)

        if failed_any and not created_any:
            order.status = "paid"
            order.updated_at = _now()

        db.commit()

    if created_any:
        send_order_notification.delay(order_id, "processing")
    if failed_any:
        send_order_notification.delay(order_id, "moogold_failed")

    return {"status": "ok", "order_id": order_id, "created_any": created_any, "failed_any": failed_any, "items": result_summary}


GAMEDROPS_STATUS_MAP = {
    "SUBMITTED": "processing",
    "PROCESSING": "processing",
    "COMPLETED": "completed",
    "CANCELED": "cancelled",
    "CANCELLED": "cancelled",
    "FAILED": "failed",
    "REFUND": "refunded",
    "REFUNDED": "refunded",
}


def _map_gamedrops_status(raw_status: Any) -> Optional[str]:
    if raw_status is None:
        return None
    return GAMEDROPS_STATUS_MAP.get(str(raw_status).strip().upper())


def _extract_gamedrops_status(response: dict) -> Optional[str]:
    if not isinstance(response, dict):
        return None

    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    candidates = [
        response.get("orderStatus"),
        response.get("order_status"),
        response.get("status"),
        data.get("orderStatus"),
        data.get("order_status"),
        data.get("status"),
    ]
    for candidate in candidates:
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip().upper()
    return None


def _get_gamedrops_order_status(transaction_id: str) -> dict:
    from app.services.gamedrops import GameDropsClient

    async def _get():
        client = GameDropsClient()
        try:
            return await client.get_order_status(transaction_id)
        finally:
            await client.close()

    return asyncio.run(_get())


class _GameDropsStatusSyncLock:
    def __init__(self, redis_lock, ttl_seconds: int):
        self._redis_lock = redis_lock
        self._ttl_seconds = ttl_seconds

    def extend(self) -> bool:
        try:
            self._redis_lock.extend(self._ttl_seconds, replace_ttl=True)
            return True
        except Exception:
            logger.warning("GameDrops status sync lock ownership was lost during extend", exc_info=True)
            return False

    def owned(self) -> bool:
        try:
            return bool(self._redis_lock.owned())
        except Exception:
            logger.warning("Failed to verify GameDrops status sync lock ownership", exc_info=True)
            return False

    def release(self) -> None:
        try:
            if self.owned():
                self._redis_lock.release()
        except Exception:
            logger.exception("Failed to release GameDrops status sync lock")


def _acquire_gamedrops_status_sync_lock(ttl_seconds: int = 120):
    try:
        import redis

        redis_client = redis.Redis.from_url(settings.REDIS_URL)
        redis_lock = redis_client.lock(
            "lock:gamedrops_status_sync",
            timeout=ttl_seconds,
            blocking=False,
            thread_local=False,
        )
        if not redis_lock.acquire(blocking=False):
            return None
        return _GameDropsStatusSyncLock(redis_lock, ttl_seconds)
    except Exception:
        logger.exception("Failed to acquire GameDrops status sync Redis lock")
        return None


@shared_task(name="app.services.moogold_fulfillment.sync_gamedrops_order_statuses")
def sync_gamedrops_order_statuses(order_id: int | None = None) -> dict:
    """Poll existing GameDrops fulfillments and reconcile local order state.

    This task only checks statuses for already-created provider orders. It never
    creates a new GameDrops order and is safe to run periodically or manually for
    a single local order id, for example: sync_gamedrops_order_statuses.delay(41).
    """
    status_lock = _acquire_gamedrops_status_sync_lock()
    if status_lock is None:
        return {"status": "skipped", "reason": "lock_not_acquired", "order_id": order_id}

    from app.models.models import MooGoldFulfillment, Order
    from app.services.notifications import send_order_notification

    checked = 0
    updated = 0
    errors = 0
    notifications: list[int] = []
    items: list[dict[str, Any]] = []
    lock_lost = False

    try:
        with SyncSessionLocal() as db:
            query = (
                select(MooGoldFulfillment)
                .join(Order, MooGoldFulfillment.order_id == Order.id)
                .options(joinedload(MooGoldFulfillment.order))
                .where(
                    MooGoldFulfillment.status == "processing",
                    func.lower(Order.provider).in_(["gamedrops", "gamesdrop"]),
                )
                .order_by(MooGoldFulfillment.updated_at.asc())
                .limit(100)
            )
            if order_id is not None:
                query = query.where(MooGoldFulfillment.order_id == int(order_id))

            fulfillments = db.execute(query).scalars().all()

            for fulfillment in fulfillments:
                checked += 1
                transaction_id = fulfillment.partner_order_id
                order = fulfillment.order
                if not transaction_id or not order:
                    errors += 1
                    fulfillment.error_message = "Missing GameDrops transactionId or local order"
                    fulfillment.updated_at = _now()
                    db.commit()
                    continue

                previous_order_status = order.status
                try:
                    if not status_lock.extend():
                        lock_lost = True
                        items.append({
                            "fulfillment_id": fulfillment.id,
                            "order_id": fulfillment.order_id,
                            "transaction_id": transaction_id,
                            "status": "lock_lost",
                        })
                        break

                    response = _get_gamedrops_order_status(transaction_id)

                    if not status_lock.extend() or not status_lock.owned():
                        lock_lost = True
                        items.append({
                            "fulfillment_id": fulfillment.id,
                            "order_id": fulfillment.order_id,
                            "transaction_id": transaction_id,
                            "status": "lock_lost",
                        })
                        break

                    raw_status = _extract_gamedrops_status(response)
                    mapped_status = _map_gamedrops_status(raw_status)

                    fulfillment.response_payload = _json_dump(response)
                    fulfillment.error_message = None
                    fulfillment.updated_at = _now()

                    order.provider_status = mapped_status or raw_status or order.provider_status
                    order.provider_response = response
                    order.updated_at = _now()

                    if mapped_status:
                        fulfillment.status = mapped_status
                        updated += 1
                        final_order_status = update_local_order_status_from_fulfillments(db, order.id)
                        if previous_order_status != "completed" and final_order_status == "completed":
                            notifications.append(order.id)
                    else:
                        final_order_status = order.status

                    db.commit()
                    items.append({
                        "fulfillment_id": fulfillment.id,
                        "order_id": fulfillment.order_id,
                        "transaction_id": transaction_id,
                        "raw_status": raw_status,
                        "mapped_status": mapped_status,
                        "order_status": final_order_status,
                    })
                except Exception as exc:
                    errors += 1
                    db.rollback()
                    fulfillment = db.get(MooGoldFulfillment, fulfillment.id)
                    if fulfillment:
                        fulfillment.error_message = str(exc)[:2000]
                        fulfillment.updated_at = _now()
                        db.commit()
                    logger.exception("Failed to sync GameDrops status for fulfillment %s", getattr(fulfillment, "id", None))
                    items.append({
                        "fulfillment_id": getattr(fulfillment, "id", None),
                        "order_id": getattr(fulfillment, "order_id", None),
                        "transaction_id": transaction_id,
                        "status": "error",
                        "error": str(exc),
                    })

        for notify_order_id in sorted(set(notifications)):
            send_order_notification.delay(notify_order_id, "completed")

        return {
            "status": "ok",
            "order_id": order_id,
            "checked": checked,
            "updated": updated,
            "errors": errors,
            "lock_lost": lock_lost,
            "completed_notifications": sorted(set(notifications)),
            "items": items,
        }
    finally:
        status_lock.release()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fulfill_order_via_moogold(self, order_id: int) -> dict:
    """Create provider order(s) after a local order is paid.

    The task name is kept for compatibility with existing imports, but GamesDrop is
    used when PROVIDER_AUTO_FULFILL_ENABLED=true. MooGold remains as legacy fallback.
    """
    if settings.PROVIDER_AUTO_FULFILL_ENABLED:
        return _fulfill_order_via_gamedrops(order_id)
    return _fulfill_order_via_moogold(order_id)
