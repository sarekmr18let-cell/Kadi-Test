from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timezone
import json

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_admin
from app.models.models import (
    User, Order, OrderItem, Product, ProductVariation, Category,
    Transaction, PromoCode, P2PCard, P2PPaymentSession, P2PIncomingPayment, BalanceTopUp, MooGoldFulfillment
)
from app.schemas.schemas import (
    DashboardStats, OrderResponse,
    ProductCreate, ProductResponse, CategoryCreate, CategoryResponse,
    UserResponse, OrderStatusUpdate, ProductVariationCreate, ProductVariationUpdate, ProductVariationResponse,
    P2PCardCreate, P2PCardUpdate, P2PCardResponse, P2PPaymentSessionResponse, P2PIncomingPaymentResponse,
    BalanceTopUpResponse, BalanceTopUpAdminUpdate
)
from app.services.notifications import send_order_notification
from app.services.p2p import count_promo_usage_if_needed, clean_card_number, card_last4, credit_balance_topup, expire_old_balance_topups, parse_incoming_payment_payload, process_incoming_p2p_payment
from app.services.moogold_fulfillment import fulfill_order_via_moogold











# KADI_BUYER_COMPLETED_DIRECT_NOTIFY_FORCE_V2
async def _kadi_send_completed_direct_to_buyer(db, order) -> None:
    """
    Sends direct Telegram message to buyer when admin marks order completed.
    Must never break admin API.
    """

    # Disabled: buyer now receives the new short delivery message below.
    return
    try:
        if db is None or order is None:
            return

        user_id = getattr(order, "user_id", None)
        if not user_id:
            return

        from sqlalchemy import text

        result = await db.execute(
            text("SELECT telegram_id FROM users WHERE id = :user_id LIMIT 1"),
            {"user_id": user_id}
        )
        row = result.first()

        if not row or not row[0]:
            try:
                logger.warning("KADI completed notify: telegram_id not found for user_id=%s", user_id)
            except Exception:
                print("KADI completed notify: telegram_id not found for user_id", user_id)
            return

        telegram_id = row[0]

        order_number = getattr(order, "order_number", None) or getattr(order, "id", "unknown")
        amount = getattr(order, "total_amount", 0)

        try:
            amount_text = f"{int(float(amount or 0)):,}".replace(",", " ")
        except Exception:
            amount_text = str(amount or 0)

        message = (
            "✅ Заказ выполнен\n\n"
            f"Заказ: #{order_number}\n"
            f"Сумма: {amount_text} UZS\n\n"
            "Спасибо за покупку в KADI."
        )

        from app.services.notifications import send_telegram_message_sync
        send_telegram_message_sync(telegram_id, message)

        try:
            logger.warning("KADI completed notify sent to buyer telegram_id=%s order=%s", telegram_id, order_number)
        except Exception:
            print("KADI completed notify sent", telegram_id, order_number)

    except Exception as exc:
        try:
            logger.warning("KADI completed notify failed: %s", exc)
        except Exception:
            print("KADI completed notify failed:", exc)


# KADI_NOTIFY_USER_ORDER_COMPLETED_V1
async def _kadi_notify_user_order_completed(session, order) -> None:
    """
    Short buyer notification after admin marks order as completed.
    Public message does not expose provider names.
    """
    try:
        from datetime import timedelta
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.models import User, OrderItem, ProductVariation
        from app.services.notifications import send_telegram_message_sync

        user_id = getattr(order, "user_id", None)
        if not user_id:
            print("KADI completed notify: no user_id")
            return

        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user or not getattr(user, "telegram_id", None):
            print("KADI completed notify: telegram_id not found for user_id", user_id)
            return

        order_model = type(order)

        order_result = await session.execute(
            select(order_model)
            .where(order_model.id == order.id)
            .options(
                selectinload(order_model.items)
                .selectinload(OrderItem.variation)
                .selectinload(ProductVariation.product)
            )
        )
        full_order = order_result.scalar_one_or_none() or order

        short_id = getattr(full_order, "id", None) or "?"

        created_at = getattr(full_order, "created_at", None)
        date_text = ""
        if created_at:
            # DB time is UTC, Uzbekistan is UTC+5
            date_text = (created_at + timedelta(hours=5)).strftime("%d.%m.%Y, %H:%M")

        product_name = None
        item_lines = []

        for item in getattr(full_order, "items", []) or []:
            variation = getattr(item, "variation", None)
            item_name = getattr(variation, "name", None) if variation else None
            item_name = item_name or "Товар"

            product = getattr(variation, "product", None) if variation else None
            if product and getattr(product, "name", None) and not product_name:
                product_name = product.name

            qty = getattr(item, "quantity", 1) or 1
            try:
                qty_int = int(qty)
            except Exception:
                qty_int = 1

            if qty_int > 1:
                item_lines.append(f"📦 {item_name} x{qty_int}")
            else:
                item_lines.append(f"📦 {item_name}")

        product_name = product_name or "Товар"

        region = (
            getattr(full_order, "target_region_label", None)
            or getattr(full_order, "target_region", None)
        )

        recipient = (
            getattr(full_order, "verified_target_name", None)
            or getattr(full_order, "target_username", None)
            or getattr(full_order, "target_id", None)
        )

        category_line = f"📂 {product_name}"
        if region:
            category_line += f" · {region}"

        lines = [
            f"✅ Заказ #{short_id} доставлен!",
            "",
        ]

        if date_text:
            lines.append(f"📅 {date_text}")

        lines.append(category_line)

        if item_lines:
            lines.extend(item_lines)

        if recipient:
            lines.append(f"👤 {recipient}")

        lines.extend([
            "",
            "Заказ выполнен.",
        ])

        message = "\n".join(lines)

        send_telegram_message_sync(str(user.telegram_id), message)

        print("KADI completed buyer notify sent:", user.telegram_id, short_id)

    except Exception as exc:
        print("KADI completed buyer notify failed:", exc)

def _kadi_format_uzs(value) -> str:
    try:
        return f"{int(float(value or 0)):,}".replace(",", " ")
    except Exception:
        return str(value or 0)


def _kadi_log_warning(message: str, *args):
    try:
        log = globals().get("logger")
        if log:
            log.warning(message, *args)
        else:
            print(message % args if args else message)
    except Exception:
        pass


def _kadi_get_admin_chat_id():
    try:
        from app.core.config import settings
        for name in ("ADMIN_TG_ID", "ADMIN_CHAT_ID", "ADMIN_TELEGRAM_ID", "ADMIN_ID"):
            value = getattr(settings, name, None)
            if value:
                return value
    except Exception:
        pass

    try:
        import os
        for name in ("ADMIN_TG_ID", "ADMIN_CHAT_ID", "ADMIN_TELEGRAM_ID", "ADMIN_ID"):
            value = os.getenv(name)
            if value:
                return value
    except Exception:
        pass

    return None


def _kadi_send_telegram_safe(chat_id, message: str) -> None:
    if not chat_id:
        return

    try:
        from app.services.notifications import send_telegram_message_sync
        send_telegram_message_sync(chat_id, message)
    except Exception as exc:
        _kadi_log_warning("KADI direct Telegram notify failed: %s", exc)


def _kadi_safe_celery_delay(task, *args, **kwargs):
    """
    MVP mode: Celery task errors must never break checkout/admin API.
    """
    try:
        delay = getattr(task, "delay")
        return delay(*args, **kwargs)
    except Exception as exc:
        _kadi_log_warning("KADI skipped Celery task %s: %s", getattr(task, "__name__", task), exc)
        return None


# KADI_SAFE_ALL_CELERY_DELAY_V4
def _kadi_safe_celery_delay(task, *args, **kwargs):
    """
    MVP mode: Celery/Rabbit/Redis task errors must never break checkout/admin API.
    """
    try:
        delay = getattr(task, "delay")
        return delay(*args, **kwargs)
    except Exception as exc:
        try:
            logger.warning("KADI skipped Celery task %s: %s", getattr(task, "__name__", task), exc)
        except Exception:
            try:
                print("KADI skipped Celery task:", task, exc)
            except Exception:
                pass
        return None


# KADI_DISABLE_CELERY_ORDER_NOTIFY_V3
def _kadi_order_notify_safe_no_celery(*args, **kwargs):
    """
    MVP mode: order notification must never break checkout/admin actions.
    Celery broker is currently unavailable/misconfigured, so we skip task safely.
    """
    try:
        logger.warning("KADI skipped Celery order notification args=%s kwargs=%s", args, kwargs)
    except Exception:
        try:
            print("KADI skipped Celery order notification", args, kwargs)
        except Exception:
            pass
    return None


router = APIRouter()

def product_payload_for_db(product: ProductCreate) -> dict:
    data = product.model_dump()
    data["region_options"] = json.dumps(data.get("region_options") or [], ensure_ascii=False)
    return data


class P2PParserTestRequest(BaseModel):
    raw_text: str = Field(..., min_length=5)
    source: str = "admin_test"
    amount: Optional[float] = None
    card_last4: Optional[str] = None
    external_id: Optional[str] = None


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    # Total users
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar()

    # Total orders & revenue
    result = await db.execute(select(func.count(Order.id)))
    total_orders = result.scalar()

    result = await db.execute(
        select(func.sum(Order.total_amount)).where(Order.status == "completed")
    )
    total_revenue = result.scalar() or 0.0

    # Today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    )
    today_orders = result.scalar()

    result = await db.execute(
        select(func.sum(Order.total_amount)).where(
            Order.created_at >= today_start,
            Order.status == "completed"
        )
    )
    today_revenue = result.scalar() or 0.0

    # Pending orders
    result = await db.execute(
        select(func.count(Order.id)).where(Order.status.in_(["paid", "payment_submitted"]))
    )
    pending_orders = result.scalar()

    return DashboardStats(
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        today_orders=today_orders,
        today_revenue=round(today_revenue, 2),
        pending_orders=pending_orders,
    )



@router.get("/system/check")
async def system_check(
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only readiness checklist for safe VPS testing.

    This endpoint does not mutate money/order data. It is meant to show what is
    ready before running real P2P/MooGold tests.
    """
    checks = []

    def add(name: str, ok: bool, message: str, severity: str = "info", meta: Optional[dict] = None):
        checks.append({
            "name": name,
            "ok": bool(ok),
            "severity": severity if not ok else "ok",
            "message": message,
            "meta": meta or {},
        })

    # Database
    try:
        await db.execute(text("SELECT 1"))
        add("database", True, "PostgreSQL connection works")
    except Exception as exc:
        add("database", False, f"PostgreSQL failed: {exc}", "critical")

    # Redis
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        pong = await r.ping()
        await r.aclose()
        add("redis", bool(pong), "Redis connection works" if pong else "Redis did not reply", "critical")
    except Exception as exc:
        add("redis", False, f"Redis check failed: {exc}", "warning")

    add("jwt_secret", bool(settings.JWT_SECRET and len(settings.JWT_SECRET) >= 32), "JWT_SECRET is long enough" if settings.JWT_SECRET and len(settings.JWT_SECRET) >= 32 else "JWT_SECRET must be at least 32 chars", "critical")
    add("bot_token", bool(settings.BOT_TOKEN and ':' in settings.BOT_TOKEN), "BOT_TOKEN looks configured" if settings.BOT_TOKEN and ':' in settings.BOT_TOKEN else "BOT_TOKEN is missing or invalid", "critical")
    add("admin_tg_id", bool(str(settings.ADMIN_TG_ID or '').strip()), "ADMIN_TG_ID is configured" if settings.ADMIN_TG_ID else "ADMIN_TG_ID is missing", "warning")
    add("internal_bot_secret", bool(settings.INTERNAL_BOT_SECRET and len(settings.INTERNAL_BOT_SECRET) >= 20), "INTERNAL_BOT_SECRET is configured" if settings.INTERNAL_BOT_SECRET and len(settings.INTERNAL_BOT_SECRET) >= 20 else "Set a long INTERNAL_BOT_SECRET", "critical")
    add("p2p_webhook_secret", bool(settings.P2P_WEBHOOK_SECRET and len(settings.P2P_WEBHOOK_SECRET) >= 20), "P2P_WEBHOOK_SECRET is configured" if settings.P2P_WEBHOOK_SECRET and len(settings.P2P_WEBHOOK_SECRET) >= 20 else "Set a long P2P_WEBHOOK_SECRET", "critical")
    add("webapp_https", str(settings.WEBAPP_URL).startswith("https://"), f"WEBAPP_URL={settings.WEBAPP_URL}", "critical")

    moogold_ready = bool(settings.MOOGOLD_TEST_MODE or (settings.MOOGOLD_PARTNER_ID and settings.MOOGOLD_SECRET_KEY))
    add("moogold", moogold_ready, "MooGold is in TEST MODE" if settings.MOOGOLD_TEST_MODE else "MooGold credentials are configured", "critical")
    add("moogold_auto", bool(settings.MOOGOLD_AUTO_FULFILL_ENABLED), "Auto fulfillment is enabled" if settings.MOOGOLD_AUTO_FULFILL_ENABLED else "MOOGOLD_AUTO_FULFILL_ENABLED is false", "warning")
    add("p2p_test_mode", bool(settings.P2P_TEST_MODE), "P2P test mode is enabled" if settings.P2P_TEST_MODE else "P2P test mode is disabled", "info")

    # Data readiness
    active_cards = (await db.execute(select(func.count(P2PCard.id)).where(P2PCard.is_active == True))).scalar() or 0
    total_cards = (await db.execute(select(func.count(P2PCard.id)))).scalar() or 0
    add("p2p_cards", active_cards > 0, f"Active cards: {active_cards} / total cards: {total_cards}", "critical")

    products_count = (await db.execute(select(func.count(Product.id)).where(Product.is_active == True))).scalar() or 0
    variations_count = (await db.execute(select(func.count(ProductVariation.id)).where(ProductVariation.is_active == True))).scalar() or 0
    unmapped_variations = (await db.execute(select(func.count(ProductVariation.id)).where(ProductVariation.is_active == True, ProductVariation.moogold_variation_id == None))).scalar() or 0
    add("catalog", products_count > 0 and variations_count > 0, f"Active products: {products_count}, active variations: {variations_count}", "warning")
    add("moogold_mapping", unmapped_variations == 0, f"Variations without moogold_variation_id: {unmapped_variations}", "warning")

    pending_topups = (await db.execute(select(func.count(BalanceTopUp.id)).where(BalanceTopUp.status == "pending"))).scalar() or 0
    review_topups = (await db.execute(select(func.count(BalanceTopUp.id)).where(BalanceTopUp.status == "needs_review"))).scalar() or 0
    failed_fulfillments = (await db.execute(select(func.count(MooGoldFulfillment.id)).where(MooGoldFulfillment.status == "failed"))).scalar() or 0
    add("finance_attention", review_topups == 0 and failed_fulfillments == 0, f"Needs-review topups: {review_topups}, failed MooGold fulfillments: {failed_fulfillments}", "warning")

    critical_failed = [c for c in checks if not c["ok"] and c["severity"] == "critical"]
    warnings = [c for c in checks if not c["ok"] and c["severity"] == "warning"]
    return {
        "status": "ready" if not critical_failed else "not_ready",
        "critical_failed": len(critical_failed),
        "warnings": len(warnings),
        "test_modes": {
            "p2p_test_mode": settings.P2P_TEST_MODE,
            "moogold_test_mode": settings.MOOGOLD_TEST_MODE,
        },
        "runtime": {
            "webapp_url": settings.WEBAPP_URL,
            "frontend_url": settings.FRONTEND_URL,
            "payment_ttl_minutes": settings.P2P_PAYMENT_TTL_MINUTES,
            "topup_min_amount": settings.WALLET_TOPUP_MIN_AMOUNT,
            "topup_max_amount": settings.WALLET_TOPUP_MAX_AMOUNT,
            "pending_topups": pending_topups,
        },
        "checks": checks,
    }


@router.post("/system/p2p/parse-test")
async def p2p_parse_test(
    payload: P2PParserTestRequest,
    admin: dict = Depends(get_current_admin),
):
    """Parse a HUMO/CardXabar text without changing balances or orders."""
    parsed = parse_incoming_payment_payload(
        raw_text=payload.raw_text,
        source=payload.source,
        amount=payload.amount,
        card_last4_value=payload.card_last4,
    )
    return {"status": "parsed", "will_mutate": False, "parsed": parsed}


@router.post("/system/p2p/process-test")
async def p2p_process_test(
    payload: P2PParserTestRequest,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Run the real P2P matching code from admin panel, only when P2P_TEST_MODE=true.

    This can credit a pending balance top-up, so it is intentionally disabled by
    default. Use it later for controlled end-to-end tests.
    """
    if not settings.P2P_TEST_MODE:
        raise HTTPException(status_code=403, detail="P2P_TEST_MODE=false. Enable it in .env only for controlled testing.")

    incoming = await process_incoming_p2p_payment(
        db=db,
        source=payload.source,
        raw_text=payload.raw_text,
        amount=payload.amount,
        card_last4_value=payload.card_last4,
        external_id=payload.external_id,
    )
    await db.commit()
    await db.refresh(incoming)
    return {
        "status": "processed",
        "incoming_payment_id": incoming.id,
        "incoming_status": incoming.status,
        "matched_topup_id": incoming.matched_topup_id,
        "matched_user_id": incoming.matched_user_id,
        "matched_order_id": incoming.matched_order_id,
    }


@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(Order).options(selectinload(Order.items).selectinload(OrderItem.variation))
    if status:
        query = query.where(Order.status == status)

    query = query.order_by(Order.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    VALID_STATUSES = {"created", "awaiting_payment", "payment_submitted", "paid", "processing", "completed", "cancelled", "refunded"}
    if status_update.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    previous_status = order.status
    order.status = status_update.status
    order.updated_at = datetime.utcnow()
    if status_update.status in {"paid", "processing", "completed"} and previous_status not in {"paid", "processing", "completed"}:
        order.paid_at = order.paid_at or datetime.utcnow()
        await count_promo_usage_if_needed(db, order)

    # If completed, create transaction once
    if status_update.status == "completed" and previous_status != "completed":
        transaction = Transaction(
            user_id=order.user_id,
            order_id=order.id,
            type="withdrawal",
            amount=order.total_amount,
            currency=order.currency,
            status="completed",
            description=f"Order #{order.order_number} completed",
        )
        db.add(transaction)

    should_fulfill = status_update.status == "paid" and previous_status != "paid"

    await db.commit()
    # KADI_CALL_BUYER_COMPLETED_DIRECT_NOTIFY_FORCE_V2
    try:
        _kadi_new_status = getattr(status_update, 'status', None) if 'status_update' in locals() else locals().get('status')
        if str(_kadi_new_status).split('.')[-1].lower() == 'completed':
            await _kadi_send_completed_direct_to_buyer(locals().get('db') or locals().get('session'), order)
    except Exception as exc:
        try:
            logger.warning('KADI completed buyer notify wrapper failed: %s', exc)
        except Exception:
            print('KADI completed buyer notify wrapper failed:', exc)

    # Notify user
    _kadi_order_notify_safe_no_celery(order.id, status_update.status)

    # If admin manually confirms a payment, automatically submit the order to MooGold.
    if should_fulfill:
        _kadi_safe_celery_delay(fulfill_order_via_moogold, order.id)

    # KADI_CALL_USER_ORDER_COMPLETED_NOTIFY_V1
    await _kadi_notify_user_order_completed(locals().get("db") or locals().get("session"), order)
    return {"status": "success", "order_id": order_id, "new_status": status_update.status, "moogold_queued": should_fulfill}


@router.post("/orders/{order_id}/fulfill")
async def fulfill_order_now(
    order_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually queue a paid order for MooGold fulfillment.

    Use this when a payment was approved manually or when a previous MooGold
    attempt failed after missing credentials/product mapping.
    """
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in {"paid", "processing"}:
        raise HTTPException(status_code=400, detail=f"Order must be paid before MooGold fulfillment. Current status: {order.status}")

    _kadi_safe_celery_delay(fulfill_order_via_moogold, order.id)
    return {"status": "queued", "order_id": order.id}


@router.get("/products", response_model=List[ProductResponse])
async def list_admin_products(
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.variations))
        .order_by(Product.sort_order)
    )
    return result.scalars().all()


@router.post("/products")
async def create_product(
    product: ProductCreate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    # Validate category exists
    result = await db.execute(select(Category).where(Category.id == product.category_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Category not found")

    new_product = Product(**product_payload_for_db(product))
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    return new_product


@router.put("/products/{product_id}")
async def update_product(
    product_id: int,
    product: ProductCreate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    # Validate category if changed
    if product.category_id != existing.category_id:
        result = await db.execute(select(Category).where(Category.id == product.category_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Category not found")

    for key, value in product_payload_for_db(product).items():
        setattr(existing, key, value)

    existing.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(existing)
    return existing


@router.post("/products/{product_id}/variations", response_model=ProductVariationResponse)
async def create_product_variation(
    product_id: int,
    variation: ProductVariationCreate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    new_variation = ProductVariation(product_id=product_id, **variation.model_dump())
    db.add(new_variation)
    await db.commit()
    await db.refresh(new_variation)
    return new_variation


@router.put("/variations/{variation_id}", response_model=ProductVariationResponse)
async def update_product_variation(
    variation_id: int,
    variation: ProductVariationUpdate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ProductVariation).where(ProductVariation.id == variation_id))
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Variation not found")

    for key, value in variation.model_dump().items():
        setattr(existing, key, value)

    await db.commit()
    await db.refresh(existing)
    return existing


@router.delete("/variations/{variation_id}")
async def delete_product_variation(
    variation_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ProductVariation).where(ProductVariation.id == variation_id))
    variation = result.scalar_one_or_none()
    if not variation:
        raise HTTPException(status_code=404, detail="Variation not found")

    variation.is_active = False
    await db.commit()
    return {"status": "success", "message": "Variation deactivated"}


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False
    await db.commit()
    return {"status": "success", "message": "Product deactivated"}


@router.post("/categories")
async def create_category(
    category: CategoryCreate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    # Check for duplicate slug
    result = await db.execute(select(Category).where(Category.slug == category.slug))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category slug already exists")

    new_category = Category(**category.model_dump())
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)
    return new_category


@router.get("/categories", response_model=List[CategoryResponse])
async def list_admin_categories(
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Category).order_by(Category.sort_order))
    return result.scalars().all()


@router.get("/users")
async def list_users(
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    if search and len(search) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query too long (max 100 characters)"
        )
    
    query = select(User)
    if search:
        query = query.where(
            (User.username.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.telegram_id.cast(str).ilike(f"%{search}%"))
        )

    query = query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_blocked = True
    await db.commit()
    return {"status": "success", "message": "User blocked"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_blocked = False
    await db.commit()
    return {"status": "success", "message": "User unblocked"}


@router.post("/promo-codes")
async def create_promo_code(
    code: str,
    type: str,
    value: float,
    min_order_amount: float = 0.0,
    max_discount: Optional[float] = None,
    usage_limit: Optional[int] = None,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    VALID_TYPES = {"fixed", "percent"}
    if type not in VALID_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Type must be one of: {VALID_TYPES}")

    # Validate code
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code must not be empty")
    if len(code) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code must be at least 3 characters long")
    if len(code) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code must be at most 50 characters long")

    # Validate value
    if value < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Value must be non-negative")
    if value > 100000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Value must be at most 100000")

    # Validate min_order_amount
    if min_order_amount < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_order_amount must be non-negative")

    # Validate usage_limit
    if usage_limit is not None and usage_limit < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="usage_limit must be at least 1")

    # Validate max_discount
    if max_discount is not None and max_discount < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_discount must be non-negative")

    # Validate date range
    if valid_from is not None and valid_until is not None and valid_until < valid_from:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="valid_until must be after or equal to valid_from")

    # Check for duplicate code
    result = await db.execute(select(PromoCode).where(PromoCode.code == code.upper()))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promo code already exists")

    new_promo = PromoCode(
        code=code.upper(),
        type=type,
        value=value,
        min_order_amount=min_order_amount,
        max_discount=max_discount,
        usage_limit=usage_limit,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    db.add(new_promo)
    await db.commit()
    await db.refresh(new_promo)
    return new_promo


# ============= P2P Card Pool / Parser Admin =============
@router.get("/p2p/cards", response_model=List[P2PCardResponse])
async def list_p2p_cards(
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(P2PCard).order_by(P2PCard.sort_order, P2PCard.id))
    return result.scalars().all()


@router.post("/p2p/cards", response_model=P2PCardResponse)
async def create_p2p_card(
    card: P2PCardCreate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    cleaned = clean_card_number(card.card_number)
    if card.max_amount is not None and card.max_amount < card.min_amount:
        raise HTTPException(status_code=400, detail="max_amount must be greater than or equal to min_amount")

    new_card = P2PCard(
        **card.model_dump(exclude={"card_number"}),
        card_number=cleaned,
        last4=card_last4(cleaned),
    )
    db.add(new_card)
    await db.commit()
    await db.refresh(new_card)
    return new_card


@router.put("/p2p/cards/{card_id}", response_model=P2PCardResponse)
async def update_p2p_card(
    card_id: int,
    card: P2PCardUpdate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(P2PCard).where(P2PCard.id == card_id))
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="P2P card not found")
    if card.max_amount is not None and card.max_amount < card.min_amount:
        raise HTTPException(status_code=400, detail="max_amount must be greater than or equal to min_amount")

    data = card.model_dump()
    data["card_number"] = clean_card_number(data["card_number"])
    data["last4"] = card_last4(data["card_number"])
    for key, value in data.items():
        setattr(existing, key, value)
    existing.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(existing)
    return existing


@router.delete("/p2p/cards/{card_id}")
async def deactivate_p2p_card(
    card_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(P2PCard).where(P2PCard.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="P2P card not found")
    card.is_active = False
    card.updated_at = datetime.utcnow()
    await db.commit()
    return {"status": "success", "message": "P2P card deactivated"}


@router.get("/p2p/sessions", response_model=List[P2PPaymentSessionResponse])
async def list_p2p_sessions(
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(P2PPaymentSession).options(selectinload(P2PPaymentSession.card)).order_by(P2PPaymentSession.created_at.desc())
    if status_filter:
        query = query.where(P2PPaymentSession.status == status_filter)
    query = query.offset((max(page, 1) - 1) * min(limit, 100)).limit(min(limit, 100))
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/p2p/incoming", response_model=List[P2PIncomingPaymentResponse])
async def list_p2p_incoming_payments(
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(P2PIncomingPayment).order_by(P2PIncomingPayment.created_at.desc())
    if status_filter:
        query = query.where(P2PIncomingPayment.status == status_filter)
    query = query.offset((max(page, 1) - 1) * min(limit, 100)).limit(min(limit, 100))
    result = await db.execute(query)
    return result.scalars().all()




@router.get("/p2p/topups", response_model=List[BalanceTopUpResponse])
async def list_balance_topups(
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await expire_old_balance_topups(db)
    await db.commit()

    query = (
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .order_by(BalanceTopUp.created_at.desc())
    )
    if status_filter:
        query = query.where(BalanceTopUp.status == status_filter)
    query = query.offset((max(page, 1) - 1) * min(limit, 100)).limit(min(limit, 100))
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/p2p/topups/{topup_id}/review", response_model=BalanceTopUpResponse)
async def review_balance_topup(
    topup_id: int,
    payload: BalanceTopUpAdminUpdate,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(BalanceTopUp.id == topup_id)
    )
    topup = result.scalar_one_or_none()
    if not topup:
        raise HTTPException(status_code=404, detail="Top-up not found")

    action = payload.action.lower().strip()
    if action == "approve":
        if topup.status == "paid":
            raise HTTPException(status_code=400, detail="Top-up is already paid")
        await credit_balance_topup(db, topup, incoming=None, note=payload.note or "Approved manually by admin")
    elif action in {"reject", "cancel"}:
        if topup.status == "paid":
            raise HTTPException(status_code=400, detail="Cannot reject a paid top-up")
        topup.status = "cancelled"
        topup.note = ((topup.note or "") + "\n" + (payload.note or f"{action.title()}ed by admin")).strip()
        topup.updated_at = datetime.utcnow()
    else:
        raise HTTPException(status_code=400, detail="action must be approve, reject, or cancel")

    await db.commit()

    result = await db.execute(
        select(BalanceTopUp)
        .options(selectinload(BalanceTopUp.card))
        .where(BalanceTopUp.id == topup.id)
    )
    return result.scalar_one()


@router.get("/transactions")
async def list_transactions(
    page: int = 1,
    limit: int = 20,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Transaction).order_by(Transaction.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    )
    return result.scalars().all()
