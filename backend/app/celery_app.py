from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "tgbot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.notifications", "app.services.moogold_fulfillment"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "cancel-expired-orders": {
            "task": "app.services.notifications.cancel_expired_orders",
            "schedule": 3600.0,  # every hour
        },
        "expire-p2p-payment-sessions": {
            "task": "app.services.notifications.expire_p2p_payment_sessions",
            "schedule": 60.0,  # every minute
        },
        "expire-balance-topups": {
            "task": "app.services.notifications.expire_balance_topups",
            "schedule": 60.0,  # every minute
        },
        "sync-gamedrops-order-statuses": {
            "task": "app.services.moogold_fulfillment.sync_gamedrops_order_statuses",
            "schedule": 30.0,  # every 30 seconds
        },
        "rescue-paid-orders-without-fulfillment": {
            "task": "app.services.moogold_fulfillment.rescue_paid_orders_without_fulfillment",
            "schedule": 60.0,  # every minute
        },
        **({
            "check-gamedrops-balance-guard": {
                "task": "app.services.moogold_fulfillment.check_gamedrops_balance_guard",
                "schedule": float(settings.GAMEDROPS_BALANCE_GUARD_INTERVAL_SECONDS),
            }
        } if settings.GAMEDROPS_BALANCE_GUARD_ENABLED else {}),
    },
)
