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

from app.core.config import settings  # noqa: E402
from app.models.models import MooGoldFulfillment, Order, Transaction, User  # noqa: E402
from app.services.refunds import _safe_to_refund_order, refund_order_to_balance  # noqa: E402


def has_refund(db, order_id):
    return db.execute(select(Transaction).where(Transaction.order_id == order_id, Transaction.type == "refund", Transaction.status == "completed")).scalar_one_or_none() is not None


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--include-failed-without-provider-order", action="store_true", help="Allow applying ambiguous failed orders without provider_order_id.")
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))
    Session = sessionmaker(bind=engine)
    with Session() as db:
        status_order_ids = db.execute(
            select(Order.id).where(
                (Order.status.in_(["refunded", "failed"]))
                | (Order.provider_status.in_(["refunded", "failed"]))
            )
        ).scalars().all()
        fulfillment_order_ids = db.execute(
            select(MooGoldFulfillment.order_id)
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
            existing_refund = has_refund(db, order.id)
            safe, reason = _safe_to_refund_order(order, fulfillments)
            ambiguous = order.status == "failed" and not order.provider_order_id and not statuses
            candidate = safe and not existing_refund and (not ambiguous or args.include_failed_without_provider_order)
            row = {"order_id": order.id, "user_id": order.user_id, "username": getattr(order.user, "username", None), "total_amount": order.total_amount, "order_status": order.status, "provider_status": order.provider_status, "fulfillment_statuses": statuses, "has_completed_refund": existing_refund, "safe_candidate": candidate, "reason": reason, "ambiguous_failed_without_provider_order": ambiguous}
            rows.append(row)
            if args.apply and candidate:
                result = refund_order_to_balance(db, order.id, reason, notify=True)
                row["apply_result"] = result.status
                db.commit()
            elif args.apply:
                row["apply_result"] = "skipped"
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
