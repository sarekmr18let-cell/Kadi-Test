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


def send_telegram_message_sync(chat_id: int, text: str, reply_markup: dict = None):
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
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")


@shared_task
def send_order_notification(order_id: int, status: str):
    """Send order status notification to user and admin."""
    from app.models.models import Order, User
    from sqlalchemy import select

    with SyncSessionLocal() as db:
        result = db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return

        result = db.execute(select(User).where(User.id == order.user_id))
        user = result.scalar_one_or_none()
        if not user:
            return

        # Status messages
        status_messages = {
            "created": "🛒 <b>New Order</b>\nYour order has been created.",
            "awaiting_payment": "⏳ <b>Awaiting Payment</b>\nPlease complete your payment.",
            "paid": "✅ <b>Payment Received</b>\nYour order is being processed.",
            "processing": "🔄 <b>Processing</b>\nYour order is being fulfilled.",
            "completed": "🎉 <b>Order Completed!</b>\nYour items have been delivered.",
            "cancelled": "❌ <b>Order Cancelled</b>\nYour order has been cancelled.",
            "refunded": "💰 <b>Refunded</b>\nYour payment has been refunded.",
        }

        message = status_messages.get(status, f"📦 Order status: {status}")
        message += f"\n\n<b>Order #</b>{escape_html(order.order_number)}"
        message += f"\n<b>Amount:</b> {escape_html(order.total_amount)} {escape_html(order.currency)}"

        # Send to user
        send_telegram_message_sync(user.telegram_id, message)

        # Send to admin
        admin_tg_id = settings.ADMIN_TG_ID
        if admin_tg_id and str(admin_tg_id).strip():
            try:
                admin_tg_id_int = int(str(admin_tg_id).strip())
                admin_message = f"🔔 <b>Order Update</b>\n\n{message}\n\nUser: @{escape_html(user.username) or escape_html(user.telegram_id)}"
                send_telegram_message_sync(admin_tg_id_int, admin_message)
            except ValueError:
                logger.error(f"Invalid ADMIN_TG_ID value: {admin_tg_id!r}")


@shared_task
def cancel_expired_orders():
    """Cancel orders that have been awaiting payment for more than 2 hours."""
    from app.models.models import Order
    from sqlalchemy import select, update
    from datetime import datetime, timezone, timedelta

    with SyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

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

    now = datetime.now(timezone.utc)
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

    now = datetime.now(timezone.utc)
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
