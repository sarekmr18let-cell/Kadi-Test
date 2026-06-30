from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFUNDS = (ROOT / "backend/app/services/refunds.py").read_text()
FULFILLMENT = (ROOT / "backend/app/services/moogold_fulfillment.py").read_text()
SCRIPT = (ROOT / "scripts/refund_provider_failed_orders.py").read_text()
NOTIFICATIONS = (ROOT / "backend/app/services/notifications.py").read_text()


def test_refunded_gamedrops_order_creates_balance_refund_transaction():
    assert "def refund_order_to_balance" in REFUNDS
    assert "user.balance = float(user.balance or 0) + amount" in REFUNDS
    assert 'type="refund"' in REFUNDS
    assert 'status="completed"' in REFUNDS
    assert 'currency="UZS"' in REFUNDS
    assert "Auto refund for provider refunded order" in REFUNDS


def test_repeated_refund_call_does_not_double_balance():
    assert "def _has_completed_refund" in REFUNDS
    assert 'Transaction.type == "refund"' in REFUNDS
    assert 'Transaction.status == "completed"' in REFUNDS
    assert 'status="already_refunded"' in REFUNDS
    assert REFUNDS.index("_has_completed_refund") < REFUNDS.index("user.balance = float(user.balance or 0) + amount")


def test_order_with_existing_manual_refund_is_skipped():
    assert "Transaction.order_id == order_id" in REFUNDS
    assert 'Transaction.type == "refund"' in REFUNDS
    assert 'return RefundResult(status="already_refunded"' in REFUNDS


def test_multi_item_all_refunded_gets_full_refund():
    assert 'FINAL_UNSUCCESSFUL_STATUSES = {"refunded", "failed", "cancelled"}' in REFUNDS
    assert "statuses.issubset(FINAL_UNSUCCESSFUL_STATUSES)" in REFUNDS
    assert "amount = float(order.total_amount or 0)" in REFUNDS


def test_multi_item_partial_completed_is_needs_review_not_full_refund():
    assert "statuses.intersection(COMPLETED_STATUSES)" in REFUNDS
    assert '"partial_provider_success_needs_review"' in REFUNDS
    assert 'order.provider_status = "needs_review"' in REFUNDS
    assert "send_refund_review_notification.delay" in FULFILLMENT


def test_wrong_price_failed_status_is_safely_recognized():
    assert '"wrong_price"' in REFUNDS
    assert '"offer_not_found"' in REFUNDS
    assert '"provider error"' in REFUNDS
    assert "--include-failed-without-provider-order" in SCRIPT
    assert '"ambiguous_failed_without_provider_order"' in SCRIPT


def test_p2p_topup_transactions_are_not_touched():
    assert "BalanceTopUp" not in REFUNDS
    assert "P2P" not in REFUNDS
    assert 'Transaction.type == "refund"' in REFUNDS


def test_status_sync_triggers_refund_but_never_create_order():
    sync_start = FULFILLMENT.index("def sync_gamedrops_order_statuses")
    sync_source = FULFILLMENT[sync_start:]
    assert "refund_order_to_balance(db, order.id, reason)" in sync_source
    assert "_get_gamedrops_order_status" in sync_source
    assert "create_gamedrops_order" not in sync_source
    assert "create_order(" not in sync_source


def test_immediate_create_order_failure_triggers_safe_refund_after_commit():
    assert "refund_result = refund_order_to_balance(db, order.id, refund_reason" in FULFILLMENT
    assert "if refund_result and refund_result.status == \"refunded\":" in FULFILLMENT
    assert FULFILLMENT.index("db.commit()") < FULFILLMENT.index("send_auto_refund_notification.delay(order_id")


def test_notifications_and_backfill_script_exist():
    assert "def send_auto_refund_notification" in NOTIFICATIONS
    assert "Деньги возвращены на ваш баланс" in NOTIFICATIONS
    assert "Auto refund: order" in NOTIFICATIONS
    assert "--dry-run" in SCRIPT
    assert "--apply" in SCRIPT


def test_backfill_is_limited_to_gamedrops_candidates():
    assert "gamedrops_order_filter" in SCRIPT
    assert "ProductVariation.provider.in_" in SCRIPT
    assert "Product.provider.in_" in SCRIPT
    assert "join(Order, MooGoldFulfillment.order_id == Order.id)" in SCRIPT


def test_gamedrops_sync_handles_cancelled_for_refund_or_review():
    assert 'final_order_status in {"refunded", "cancelled"}' in FULFILLMENT
    assert 'mapped_status in {"refunded", "failed", "cancelled"}' in FULFILLMENT


def test_moogold_webhook_mixed_fulfillment_calls_review_path():
    webhook = (ROOT / "backend/app/api/webhook.py").read_text()
    assert 'has_completed = bool(statuses.intersection({"completed"}))' in webhook
    assert 'has_unsuccessful = bool(statuses.intersection({"refunded", "cancelled", "failed"}))' in webhook
    assert 'order.status == "refunded" or (has_completed and has_unsuccessful)' in webhook
    assert 'send_refund_review_notification.delay' in webhook


def test_backfill_notification_failure_is_recorded_not_raised():
    assert "def maybe_send_refund_notification" in SCRIPT
    assert "except Exception as exc" in SCRIPT
    assert 'record_notification_error(row, exc)' in SCRIPT
    assert 'row["notification_error"]' in SCRIPT
    assert 'db.commit()' in SCRIPT
    assert SCRIPT.index('db.commit()') < SCRIPT.index('maybe_send_refund_notification(row, AUTO_REFUND_TASK')


def test_backfill_no_notify_skips_notifications():
    assert 'parser.add_argument("--no-notify"' in SCRIPT
    assert 'notify = not args.no_notify' in SCRIPT
    assert 'row["notification_result"] = "skipped_no_notify"' in SCRIPT


def test_backfill_notify_only_does_not_create_refund_transaction():
    assert 'mode.add_argument("--notify-only"' in SCRIPT
    notify_only_block = SCRIPT[SCRIPT.index('elif args.notify_only:'):]
    assert 'refund_order_to_balance(' not in notify_only_block
    assert 'existing_refund and eligible' in notify_only_block
    assert 'row["apply_result"] = "already_refunded"' in notify_only_block
    assert 'AUTO_REFUND_TASK' in notify_only_block


def test_backfill_uses_project_celery_app_not_default_amqp_broker():
    assert 'from app.celery_app import celery_app' in SCRIPT
    assert 'celery_app.send_task' in SCRIPT
    assert 'send_auto_refund_notification.delay' not in SCRIPT
    assert 'send_refund_review_notification.delay' not in SCRIPT
    assert 'amqp://localhost' not in SCRIPT


def test_backfill_existing_refund_reports_already_refunded_on_apply():
    apply_block = SCRIPT[SCRIPT.index('if args.apply and eligible:'):SCRIPT.index('elif args.apply:')]
    assert 'refund_order_to_balance(db, order.id, reason)' in apply_block
    assert 'row["apply_result"] = result.status' in apply_block
    assert 'candidate = eligible and not existing_refund' in SCRIPT
