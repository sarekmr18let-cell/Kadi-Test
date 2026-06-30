#!/usr/bin/env python3
"""Dry-run/apply safe Kadi balance refunds for provider failed/refunded orders."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker, joinedload  # noqa: E402

from app.celery_app import celery_app  # noqa: E402,F401 - ensure project Celery config is loaded, not Celery's default app
from app.core.config import settings  # noqa: E402
from app.models.models import MooGoldFulfillment, Order, OrderItem, Product, ProductVariation, Transaction  # noqa: E402
from app.services.refunds import _safe_to_refund_order, refund_order_to_balance  # noqa: E402

AUTO_REFUND_TASK = "app.services.notifications.send_auto_refund_notification"
REFUND_REVIEW_TASK = "app.services.notifications.send_refund_review_notification"


def get_completed_refund(db, order_id):
    return db.execute(
        select(Transaction).where(
            Transaction.order_id == order_id,
            Transaction.type == "refund",
            Transaction.status == "completed",
        )
    ).scalar_one_or_none()


def has_refund(db, order_id):
    return get_completed_refund(db, order_id) is not None


def send_notification(task_name, args):
    """Send a notification via the project Celery app and let callers log failures."""
    return celery_app.send_task(task_name, args=args)


def record_notification_error(row, exc):
    row["notification_error"] = f"{exc.__class__.__name__}: {exc}"


def maybe_send_refund_notification(row, task_name, args, notify):
    if not notify:
        row["notification_result"] = "skipped_no_notify"
        return
    try:
        async_result = send_notification(task_name, args)
        row["notification_result"] = "queued"
        row["notification_task_id"] = getattr(async_result, "id", None)
    except Exception as exc:  # keep committed refunds safe from broker outages
        record_notification_error(row, exc)


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--notify-only", action="store_true", help="Send notifications for orders that already have a completed refund transaction without creating refunds.")
    parser.add_argument("--no-notify", action="store_true", help="Apply refunds without queueing refund notifications.")
    parser.add_argument("--include-failed-without-provider-order", action="store_true", help="Allow applying ambiguous failed orders without provider_order_id.")
    args = parser.parse_args()

    notify = not args.no_notify
    engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))
    Session = sessionmaker(bind=engine)
    with Session() as db:
        gamedrops_order_filter = Order.provider.in_(["gamedrops", "gamesdrop"])
        gamedrops_item_order_ids = select(OrderItem.order_id).join(ProductVariation, OrderItem.variation_id == ProductVariation.id).join(Product, ProductVariation.product_id == Product.id).where(
            ProductVariation.provider.in_(["gamedrops", "gamesdrop"])
            | Product.provider.in_(["gamedrops", "gamesdrop"])
        )
        status_order_ids = db.execute(
            select(Order.id).where(
                ((Order.status.in_(["refunded", "failed"])) | (Order.provider_status.in_(["refunded", "failed"])))
                & (gamedrops_order_filter | Order.id.in_(gamedrops_item_order_ids))
            )
        ).scalars().all()
        fulfillment_order_ids = db.execute(
            select(MooGoldFulfillment.order_id)
            .join(Order, MooGoldFulfillment.order_id == Order.id)
            .where(gamedrops_order_filter | Order.id.in_(gamedrops_item_order_ids))
            .group_by(MooGoldFulfillment.order_id)
        ).scalars().all()
        candidate_order_ids = sorted(set(status_order_ids) | set(fulfillment_order_ids))
        orders = db.execute(
            select(Order)
            .options(joinedload(Order.user))
            .where(Order.id.in_(candidate_order_ids))
        ).unique().scalars().all() if candidate_order_ids else []
        rows = []
        for order in orders:
            fulfillments = db.execute(select(MooGoldFulfillment).where(MooGoldFulfillment.order_id == order.id)).scalars().all()
            statuses = [f.status for f in fulfillments]
            existing_refund = get_completed_refund(db, order.id)
            safe, reason = _safe_to_refund_order(order, fulfillments)
            ambiguous = order.status == "failed" and not order.provider_order_id and not statuses
            eligible = safe and (not ambiguous or args.include_failed_without_provider_order)
            candidate = eligible and not existing_refund
            row = {"order_id": order.id, "user_id": order.user_id, "username": getattr(order.user, "username", None), "total_amount": order.total_amount, "order_status": order.status, "provider_status": order.provider_status, "fulfillment_statuses": statuses, "has_completed_refund": bool(existing_refund), "safe_candidate": candidate, "reason": reason, "ambiguous_failed_without_provider_order": ambiguous}
            rows.append(row)
            if args.apply and eligible:
                result = refund_order_to_balance(db, order.id, reason)
                row["apply_result"] = result.status
                db.commit()
                if result.status == "refunded":
                    maybe_send_refund_notification(row, AUTO_REFUND_TASK, [order.id, result.amount, result.reason or reason], notify)
                elif result.status == "partial_provider_success_needs_review":
                    maybe_send_refund_notification(row, REFUND_REVIEW_TASK, [order.id, result.reason or reason], notify)
            elif args.apply:
                row["apply_result"] = "skipped"
            elif args.notify_only:
                if existing_refund and eligible:
                    row["apply_result"] = "already_refunded"
                    maybe_send_refund_notification(row, AUTO_REFUND_TASK, [order.id, existing_refund.amount, getattr(existing_refund, "description", None) or reason], notify)
                else:
                    row["apply_result"] = "skipped"
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
