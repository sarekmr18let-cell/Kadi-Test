from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime, timezone
import random
import string
import json

from app.core.database import get_db
from app.services.gamedrops import GameDropsClient
from app.core.security import get_current_user
from app.models.models import Order, OrderItem, ProductVariation, PromoCode, P2PPaymentSession, User, Transaction, Product
from app.schemas.schemas import (
    OrderCreateRequest,
    OrderResponse,
    OrderPaymentRequest,
    OrderStatusUpdate,
    PromoApplyRequest,
    PromoResponse,
)
from app.services.notifications import send_order_notification
from app.services.p2p import count_promo_usage_if_needed
from app.services.moogold_fulfillment import fulfill_order_via_moogold









# KADI_NOTIFY_ADMIN_NEW_ORDER_V1

def _kadi_format_amount_safe(value) -> str:
    try:
        return f"{int(float(value)):,}".replace(",", " ")
    except Exception:
        return str(value)

def _kadi_notify_admin_new_order(order) -> None:
    """
    Notify admin when a paid order is created.
    """
    try:
        admin_chat_id = _kadi_get_admin_chat_id()
        if not admin_chat_id:
            _kadi_log_warning("KADI admin chat id not configured")
            return

        order_number = getattr(order, "order_number", None) or getattr(order, "id", "unknown")
        amount = getattr(order, "total_amount", 0)
        status = getattr(order, "status", "paid")
        user_id = getattr(order, "user_id", "unknown")

        target_id = getattr(order, "target_id", None)
        target_server = getattr(order, "target_server", None)
        target_region = (
            getattr(order, "target_region_label", None)
            or getattr(order, "target_region", None)
        )
        nickname = getattr(order, "verified_target_name", None)

        target_parts = []
        if target_id:
            target_parts.append(str(target_id))
        if target_server:
            target_parts.append(str(target_server))

        target_text = " / ".join(target_parts) if target_parts else "Открой админ-панель"

        detail_lines = [f"Target: {target_text}"]

        if nickname:
            detail_lines.append(f"Nickname: {nickname}")

        if target_region:
            detail_lines.append(f"Region: {target_region}")

        details_text = "\n".join(detail_lines)

        message = (
            "🆕 Новый оплаченный заказ\n\n"
            f"Заказ: #{order_number}\n"
            f"User ID: {user_id}\n"
            f"Сумма: {_kadi_format_amount_safe(amount)} UZS\n"
            f"Статус: {status}\n"
            f"{details_text}\n\n"
            "Открой админ-панель и нажми «✅ Выполнено» после выдачи."
        )

        _kadi_send_telegram_safe(admin_chat_id, message)
    except Exception as exc:
        _kadi_log_warning("KADI admin new order notification failed: %s", exc)

# KADI_ORDER_DIRECT_TELEGRAM_NOTIFY_V1
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




def order_response_options():
    return (selectinload(Order.items).selectinload(OrderItem.variation),)


async def load_order_for_response(db: AsyncSession, order_id: int, user_id: int | None = None) -> Order:
    query = select(Order).options(*order_response_options()).where(Order.id == order_id)
    if user_id is not None:
        query = query.where(Order.user_id == user_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

def generate_order_number() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ORD-{timestamp}-{random_suffix}"


@router.post("", response_model=OrderResponse)
async def create_order(
    request: OrderCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create an order and pay it from the user's wallet balance.

    v6 changes the main flow from direct P2P-per-order to wallet balance:
    1) User tops up balance with one locked card.
    2) Purchase deducts balance immediately.
    3) Paid order is queued for MooGold fulfillment.
    """
    user_id = int(current_user["sub"])

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_blocked:
        raise HTTPException(status_code=403, detail="User is blocked")

    # Validate items and check stock
    variation_ids = [item.variation_id for item in request.items]
    if not variation_ids:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    result = await db.execute(
        select(ProductVariation)
        .options(selectinload(ProductVariation.product))
        .where(
            ProductVariation.id.in_(variation_ids),
            ProductVariation.is_active == True,
            ProductVariation.stock_status == "instock"
        )
    )
    variations = {v.id: v for v in result.scalars().all()}

    if len(variations) != len(set(variation_ids)):
        missing = set(variation_ids) - set(variations.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Some products are unavailable or out of stock. Missing variation IDs: {missing}"
        )

    # Validate quantities and calculate totals from DB prices only
    total = 0.0
    order_items_data = []
    for item in request.items:
        var = variations[item.variation_id]

        if item.quantity < 1 or item.quantity > 10:
            raise HTTPException(
                status_code=400,
                detail=f"Quantity for {var.name} must be between 1 and 10"
            )

        item_total = var.price * item.quantity
        total += item_total
        order_items_data.append({
            "variation_id": var.id,
            "quantity": item.quantity,
            "unit_price": var.price,
            "total_price": item_total,
        })

    # Apply promo if provided
    discount = 0.0
    promo_error = None
    if request.promo_code:
        result = await db.execute(
            select(PromoCode).where(
                PromoCode.code == request.promo_code.upper(),
                PromoCode.is_active == True
            )
        )
        promo = result.scalar_one_or_none()

        if promo:
            now = datetime.utcnow()
            if promo.valid_from and promo.valid_from > now:
                promo_error = "Promo code not yet active"
            elif promo.valid_until and promo.valid_until < now:
                promo_error = "Promo code expired"
            elif promo.usage_limit and promo.usage_count >= promo.usage_limit:
                promo_error = "Promo code usage limit reached"
            elif total < promo.min_order_amount:
                promo_error = f"Minimum order amount: {promo.min_order_amount}"
            else:
                if promo.type == "percent":
                    discount = total * (promo.value / 100)
                    if promo.max_discount:
                        discount = min(discount, promo.max_discount)
                else:
                    discount = min(promo.value, total)
        else:
            promo_error = "Invalid promo code"

    if promo_error:
        raise HTTPException(status_code=400, detail=promo_error)

    # Validate product-specific account requirements (ID / server / region).
    products_by_id = {v.product.id: v.product for v in variations.values() if v.product}
    products_requiring_details = [
        p for p in products_by_id.values()
        if bool(p.requires_target_id) or bool(p.requires_server_id) or bool(p.requires_region)
    ]
    if len(products_requiring_details) > 1:
        raise HTTPException(
            status_code=400,
            detail="Cart can contain only one game/service type when account details or region are required. Create separate orders.",
        )

    target_region_label = None
    if products_requiring_details:
        product_req = products_requiring_details[0]
        if product_req.requires_target_id and not (request.target_id or "").strip():
            raise HTTPException(status_code=400, detail=f"{product_req.target_id_label or 'User ID'} is required")
        if product_req.requires_server_id and not (request.target_server or "").strip():
            raise HTTPException(status_code=400, detail=f"{product_req.target_server_label or 'Server ID'} is required")
        if product_req.requires_region:
            if not (request.target_region or "").strip():
                raise HTTPException(status_code=400, detail=f"{product_req.target_region_label or 'Region'} is required")
            try:
                region_options = json.loads(product_req.region_options or "[]")
            except Exception:
                region_options = []
            allowed_regions = {str(r.get("code")): r for r in region_options if isinstance(r, dict) and r.get("code")}
            if allowed_regions and request.target_region not in allowed_regions:
                raise HTTPException(status_code=400, detail="Selected region is not available for this product")
            if request.target_region in allowed_regions:
                target_region_label = allowed_regions[request.target_region].get("label")

    final_total = round(max(0, total - discount), 2)

    # Wallet balance check before creating a paid order.
    current_balance = round(float(user.balance or 0), 2)
    if current_balance + 0.01 < final_total:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Required {final_total} UZS, available {current_balance} UZS"
        )

    # Create paid order
    verified_target_name = getattr(request, "verified_target_name", None) or None
    verified_target_payload = getattr(request, "verified_target_payload", None) or {}

    # Server-side GameDrops verification fallback.
    # This keeps checkout safe even if Mini App does not send verified_target_name.
    target_id_for_verify = str(getattr(request, "target_id", None) or "").strip()
    target_server_for_verify = str(getattr(request, "target_server", None) or "").strip()

    if not verified_target_name and request.items and target_id_for_verify and target_server_for_verify:
        try:
            first_item = request.items[0]
            first_variation_id = getattr(first_item, "variation_id", None)

            if first_variation_id:
                variation = await db.get(ProductVariation, first_variation_id)

                if (
                    variation
                    and getattr(variation, "provider", None) == "gamedrops"
                    and getattr(variation, "provider_variation_id", None)
                ):
                    gd_client = GameDropsClient()
                    try:
                        gd_data = await gd_client.check_game_data(
                            offer_id=str(variation.provider_variation_id),
                            game_user_id=target_id_for_verify,
                            game_server_id=target_server_for_verify,
                        )

                        if isinstance(gd_data, dict):
                            gd_status = str(gd_data.get("status") or "").upper()
                            gd_name = (
                                gd_data.get("gameUserLogin")
                                or gd_data.get("nickname")
                                or gd_data.get("name")
                                or gd_data.get("username")
                            )

                            if gd_status == "VALID" and gd_name:
                                verified_target_name = str(gd_name)
                                verified_target_payload = gd_data
                    finally:
                        await gd_client.close()
        except Exception:
            # Checkout must not fail only because nickname verification failed.
            pass

    order = Order(
        order_number=generate_order_number(),
        user_id=user_id,
        status="paid",
        total_amount=final_total,
        currency="UZS",
        payment_method="wallet_balance",
        payment_amount=final_total,
        paid_at=datetime.utcnow(),
        target_id=(request.target_id or None),
        target_server=(request.target_server or None),
        target_region=(request.target_region or None),
        target_region_label=target_region_label,
        verified_target_name=verified_target_name,
        verified_target_payload=verified_target_payload,
        promo_code=request.promo_code,
        discount_amount=discount,
        partner_order_id=generate_order_number(),
    )
    db.add(order)
    await db.flush()

    # Create order items
    for item_data in order_items_data:
        order_item = OrderItem(order_id=order.id, **item_data)
        db.add(order_item)

    # Deduct balance and create a ledger transaction
    user.balance = round(current_balance - final_total, 2)
    tx = Transaction(
        user_id=user_id,
        order_id=order.id,
        type="purchase",
        amount=final_total,
        currency="UZS",
        status="completed",
        description=f"Purchase order #{order.order_number}",
    )
    db.add(tx)

    await count_promo_usage_if_needed(db, order)

    await db.commit()
    await db.refresh(order)

    # KADI_ORDER_NOTIFICATION_SAFE_V1
    try:
        _kadi_order_notify_safe_no_celery(order.id, "paid")
    except Exception as exc:
        try:
            logger.warning("KADI order notification task failed: %s", exc)
        except Exception:
            print("KADI order notification task failed:", exc)
    _kadi_safe_celery_delay(fulfill_order_via_moogold, order.id)

    # KADI_CALL_ADMIN_NEW_ORDER_NOTIFY_V1
    _kadi_notify_admin_new_order(order)
    return await load_order_for_response(db, order.id, user_id)


@router.get("/my", response_model=List[OrderResponse])
async def get_my_orders(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Order)
        .options(*order_response_options())
        .where(
            Order.user_id == int(current_user["sub"])
        ).order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await load_order_for_response(db, order_id, int(current_user["sub"]))


@router.post("/{order_id}/pay", response_model=OrderResponse)
async def submit_payment(
    order_id: int,
    request: OrderPaymentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == int(current_user["sub"]),
            Order.status.in_(["awaiting_payment", "payment_submitted"])
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or payment cannot be submitted")

    # Validate payment amount. If a P2P session exists, user must transfer the exact unique amount.
    expected_amount = order.total_amount
    result = await db.execute(
        select(P2PPaymentSession).where(
            P2PPaymentSession.order_id == order.id,
            P2PPaymentSession.status == "active",
        ).order_by(P2PPaymentSession.created_at.desc())
    )
    active_session = result.scalar_one_or_none()
    if active_session:
        expected_amount = active_session.assigned_amount

    if abs(request.payment_amount - expected_amount) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount must be exactly {expected_amount}"
        )

    # User can submit a receipt/manual confirmation, but this does NOT mean money is received.
    # Real confirmation must come from the P2P parser or from an admin.
    order.status = "payment_submitted"
    order.payment_method = request.payment_method
    order.payment_amount = request.payment_amount
    order.payment_receipt = request.payment_receipt
    order.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(order)

    # Notify admin that a manual check is needed.
    # KADI_ORDER_NOTIFICATION_SAFE_V1
    try:
        _kadi_order_notify_safe_no_celery(order.id, "payment_submitted")
    except Exception as exc:
        try:
            logger.warning("KADI order notification task failed: %s", exc)
        except Exception:
            print("KADI order notification task failed:", exc)

    return await load_order_for_response(db, order.id, int(current_user["sub"]))


@router.post("/apply-promo", response_model=PromoResponse)
async def apply_promo(
    request: PromoApplyRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PromoCode).where(
            PromoCode.code == request.code.upper(),
            PromoCode.is_active == True
        )
    )
    promo = result.scalar_one_or_none()

    if not promo:
        return PromoResponse(
            code=request.code,
            type="",
            value=0,
            discount_amount=0,
            is_valid=False,
            message="Invalid promo code"
        )

    now = datetime.utcnow()

    if promo.valid_from and promo.valid_from > now:
        return PromoResponse(code=promo.code, type=promo.type, value=promo.value, discount_amount=0, is_valid=False, message="Promo code not yet active")

    if promo.valid_until and promo.valid_until < now:
        return PromoResponse(code=promo.code, type=promo.type, value=promo.value, discount_amount=0, is_valid=False, message="Promo code expired")

    if promo.usage_limit and promo.usage_count >= promo.usage_limit:
        return PromoResponse(code=promo.code, type=promo.type, value=promo.value, discount_amount=0, is_valid=False, message="Promo code usage limit reached")

    if request.order_amount < promo.min_order_amount:
        return PromoResponse(code=promo.code, type=promo.type, value=promo.value, discount_amount=0, is_valid=False, message=f"Minimum order amount: {promo.min_order_amount}")

    if promo.type == "percent":
        discount = request.order_amount * (promo.value / 100)
        if promo.max_discount:
            discount = min(discount, promo.max_discount)
    else:
        discount = min(promo.value, request.order_amount)

    return PromoResponse(
        code=promo.code,
        type=promo.type,
        value=promo.value,
        discount_amount=round(discount, 2),
        is_valid=True,
        message="Promo applied successfully"
    )