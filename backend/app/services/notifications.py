from celery import shared_task
import httpx
import asyncio
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

# Sync engine for Celery tasks (Celery runs in sync context)
SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(SYNC_DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine)


def escape_html(text):
    """Escape special HTML characters to prevent XSS."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _normalize_lang(code: str | None) -> str:
    normalized = (code or "").lower()
    if normalized in {"ru", "uz", "en"}:
        return normalized
    return "ru"


def _as_tashkent_datetime(value):
    from datetime import timezone
    from zoneinfo import ZoneInfo

    if value is None:
        return ""
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Tashkent")).strftime("%d.%m.%Y, %H:%M")


def _localized_completed_text(lang: str) -> dict[str, str]:
    normalized = _normalize_lang(lang)
    texts = {
        "ru": {
            "delivered": "✅ Заказ #{order_number} доставлен!",
            "completed": "Заказ выполнен.",
            "admin_title": "🔔 Обновление заказа",
            "admin_user": "Пользователь:",
        },
        "uz": {
            "delivered": "✅ Buyurtma #{order_number} yetkazildi!",
            "completed": "Buyurtma bajarildi.",
            "admin_title": "🔔 Buyurtma yangilanishi",
            "admin_user": "Foydalanuvchi:",
        },
        "en": {
            "delivered": "✅ Order #{order_number} delivered!",
            "completed": "Order completed.",
            "admin_title": "🔔 Order Update",
            "admin_user": "User:",
        },
    }
    return texts[normalized]


def _variation_product_name(item) -> str:
    variation = getattr(item, "variation", None)
    product = getattr(variation, "product", None)
    return getattr(product, "name", None) or ""


def _variation_name(item) -> str:
    variation = getattr(item, "variation", None)
    return getattr(variation, "name", None) or ""


def _order_region(order) -> str:
    return getattr(order, "target_region_label", None) or getattr(order, "target_region", None) or ""


def _order_recipient(order) -> str:
    verified = getattr(order, "verified_target_name", None)
    if verified:
        return str(verified)
    target_id = getattr(order, "target_id", None) or ""
    target_server = getattr(order, "target_server", None) or ""
    if target_id and target_server:
        return f"{target_id} ({target_server})"
    return str(target_id or target_server or "")


def build_completed_order_message(order, user) -> str:
    lang = _normalize_lang(getattr(user, "language_code", None))
    text = _localized_completed_text(lang)
    order_number = escape_html(getattr(order, "order_number", ""))
    completed_at = _as_tashkent_datetime(getattr(order, "updated_at", None) or getattr(order, "created_at", None))
    items = list(getattr(order, "items", None) or [])
    product_name = _variation_product_name(items[0]) if items else ""
    region = _order_region(order)
    recipient = _order_recipient(order)

    lines = [
        text["delivered"].format(order_number=order_number),
        "",
        f"📅 {escape_html(completed_at)}",
    ]

    product_line = escape_html(product_name)
    if region:
        product_line = f"{product_line} · {escape_html(region)}" if product_line else escape_html(region)
    if product_line:
        lines.append(f"📂 {product_line}")

    for item in items:
        package = escape_html(_variation_name(item))
        quantity = int(getattr(item, "quantity", 1) or 1)
        if quantity > 1:
            package = f"{package} ×{quantity}"
        lines.append(f"📦 {package}")

    if recipient:
        lines.append(f"👤 {escape_html(recipient)}")

    lines.extend(["", text["completed"]])
    return "\n".join(lines)


def build_completed_admin_message(order, user, user_message: str) -> str:
    lang = _normalize_lang(getattr(user, "language_code", None))
    text = _localized_completed_text(lang)
    username = getattr(user, "username", None)
    user_label = f"@{escape_html(username)}" if username else escape_html(getattr(user, "telegram_id", ""))
    return f"{text['admin_title']}\n\n{user_message}\n\n{text['admin_user']} {user_label}"


def send_telegram_message_sync(chat_id: int, text: str, reply_markup: dict = None) -> bool:
    """Send message via Telegram Bot API (sync version for Celery)."""
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = httpx.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
        return False


def _notification_redis_client():
    import redis

    return redis.Redis.from_url(settings.REDIS_URL)


def _completed_notification_lock(redis_client, order_id: int):
    return redis_client.lock(
        f"lock:order_completed_notification:{order_id}",
        timeout=120,
        blocking=False,
        thread_local=False,
    )


@shared_task
def send_order_notification(order_id: int, status: str):
    """Send final completed notification only; intermediate statuses are disabled."""
    if status != "completed":
        return {"status": "disabled", "order_id": order_id, "notification_status": status}

    from app.models.models import Order, User, OrderItem, ProductVariation, Product
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    redis_client = _notification_redis_client()
    lock = _completed_notification_lock(redis_client, order_id)
    if not lock.acquire(blocking=False):
        return {"status": "duplicate", "order_id": order_id}

    marker_key = f"sent:order_completed_notification:{order_id}"
    marker_ttl_seconds = 90 * 24 * 60 * 60

    try:
        if redis_client.exists(marker_key):
            return {"status": "duplicate", "order_id": order_id}

        with SyncSessionLocal() as db:
            result = db.execute(
                select(Order)
                .options(
                    joinedload(Order.items)
                    .joinedload(OrderItem.variation)
                    .joinedload(ProductVariation.product)
                )
                .where(Order.id == order_id)
            )
            order = result.unique().scalar_one_or_none()
            if not order:
                return {"status": "not_found", "order_id": order_id}

            result = db.execute(select(User).where(User.id == order.user_id))
            user = result.scalar_one_or_none()
            if not user:
                return {"status": "user_not_found", "order_id": order_id}

            user_message = build_completed_order_message(order, user)
            user_sent = send_telegram_message_sync(user.telegram_id, user_message)
            if not user_sent:
                return {"status": "send_failed", "order_id": order_id}

            redis_client.set(marker_key, "1", ex=marker_ttl_seconds)

            admin_sent = False
            admin_tg_id = settings.ADMIN_TG_ID
            if admin_tg_id and str(admin_tg_id).strip():
                try:
                    admin_tg_id_int = int(str(admin_tg_id).strip())
                    admin_message = build_completed_admin_message(order, user, user_message)
                    admin_sent = send_telegram_message_sync(admin_tg_id_int, admin_message)
                except ValueError:
                    logger.error(f"Invalid ADMIN_TG_ID value: {admin_tg_id!r}")

            return {"status": "sent", "order_id": order_id, "user_sent": user_sent, "admin_sent": admin_sent}
    finally:
        try:
            if lock.owned():
                lock.release()
        except Exception:
            logger.exception("Failed to release completed notification lock")


@shared_task
def cancel_expired_orders():
    """Cancel orders that have been awaiting payment for more than 2 hours."""
    from app.models.models import Order
    from sqlalchemy import select, update
    from datetime import datetime, timezone, timedelta

    with SyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(hours=2)

        result = db.execute(
            select(Order).where(
                Order.status == "awaiting_payment",
                Order.created_at < cutoff
            )
        )
        expired_orders = result.scalars().all()

        for order in expired_orders:
            order.status = "cancelled"
            send_order_notification.delay(order.id, "cancelled")

        db.commit()

        return f"Cancelled {len(expired_orders)} expired orders"



@shared_task
def expire_p2p_payment_sessions():
    """Expire P2P payment sessions after their payment window ends."""
    from app.models.models import P2PPaymentSession
    from sqlalchemy import select
    from datetime import datetime, timezone

    now = datetime.utcnow()
    with SyncSessionLocal() as db:
        result = db.execute(
            select(P2PPaymentSession).where(
                P2PPaymentSession.status == "active",
                P2PPaymentSession.expires_at < now,
            )
        )
        sessions = result.scalars().all()
        for session in sessions:
            session.status = "expired"
            session.updated_at = now
        db.commit()
        return f"Expired {len(sessions)} P2P payment sessions"


@shared_task
def expire_balance_topups():
    """Expire wallet balance top-ups after their payment window ends."""
    from app.models.models import BalanceTopUp
    from sqlalchemy import select
    from datetime import datetime, timezone

    now = datetime.utcnow()
    with SyncSessionLocal() as db:
        result = db.execute(
            select(BalanceTopUp).where(
                BalanceTopUp.status == "pending",
                BalanceTopUp.expires_at < now,
            )
        )
        topups = result.scalars().all()
        for topup in topups:
            topup.status = "expired"
            topup.updated_at = now
            topup.note = ((topup.note or "") + "\nExpired automatically.").strip()
        db.commit()
        return f"Expired {len(topups)} balance top-ups"
