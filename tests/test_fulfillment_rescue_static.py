import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULFILLMENT_SOURCE = (ROOT / "backend/app/services/moogold_fulfillment.py").read_text()
CELERY_SOURCE = (ROOT / "backend/app/celery_app.py").read_text()
COMPOSE_SOURCE = (ROOT / "docker-compose.yml").read_text()
CONFIG_SOURCE = (ROOT / "backend/app/core/config.py").read_text()
MODULE = ast.parse(FULFILLMENT_SOURCE)


def function_source(name: str) -> str:
    for node in ast.walk(MODULE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(FULFILLMENT_SOURCE, node)
    raise AssertionError(f"function {name} not found")


def test_rescue_query_selects_paid_gamedrops_orders_within_rescue_window():
    source = function_source("_find_paid_orders_without_fulfillment")
    assert 'Order.status == "paid"' in source
    assert "cutoff = now - timedelta(seconds=delay_seconds)" in source
    assert "oldest_allowed = now - timedelta(seconds=max_age_seconds)" in source
    assert "Order.created_at <= cutoff" in source
    assert "Order.created_at >= oldest_allowed" in source
    assert "ProductVariation.provider" in source
    assert "Product.provider" in source
    assert '"gamedrops"' in source
    assert "MooGoldFulfillment.id == None" in source


def test_rescue_query_skips_orders_younger_than_delay_and_older_than_max_age():
    source = function_source("_find_paid_orders_without_fulfillment")
    assert "Order.created_at <= cutoff" in source
    assert "Order.created_at >= oldest_allowed" in source
    assert source.index("Order.created_at <= cutoff") < source.index("Order.created_at >= oldest_allowed")


def test_rescue_query_skips_delivered_refunded_cancelled_failed_provider_statuses():
    source = function_source("_find_paid_orders_without_fulfillment")
    assert "FINAL_PROVIDER_STATUSES" in source
    assert "func.lower(Order.provider_status).notin_" in source
    for status in ["delivered", "refunded", "cancelled", "failed"]:
        assert status in FULFILLMENT_SOURCE


def test_rescue_query_selects_null_status_fulfillment_with_missing_provider_order_id():
    source = function_source("_find_paid_orders_without_fulfillment")
    assert "non_final_fulfillment_status = or_(" in source
    assert "MooGoldFulfillment.status == None" in source
    assert "missing_provider_order_id = or_(" in source
    assert "MooGoldFulfillment.moogold_order_id == None" in source
    assert 'MooGoldFulfillment.moogold_order_id == ""' in source
    assert "missing_provider_order_id & non_final_fulfillment_status" in source
    assert "FINAL_FULFILLMENT_STATUSES" in source
    assert "notin_(list(FINAL_FULFILLMENT_STATUSES))" in source


def test_rescue_task_enqueues_fulfillment_once_with_redis_dedupe():
    source = function_source("rescue_paid_orders_without_fulfillment")
    assert "dedupe:fulfillment_rescue_enqueue" in source
    assert "_redis_set_once(dedupe_key, dedupe_ttl)" in source
    assert "fulfill_order_via_moogold.delay(order_id)" in source
    assert "reason=dedupe_ttl" in source


def test_rescue_has_admin_notification_and_summary_logging():
    rescue_source = function_source("rescue_paid_orders_without_fulfillment")
    admin_source = function_source("_send_rescue_admin_notification_once")
    assert "rescued_paid_orders_without_fulfillment checked=%s rescued=%s skipped=%s max_age_seconds=%s" in rescue_source
    assert "settings.FULFILLMENT_RESCUE_MAX_AGE_SECONDS" in rescue_source
    assert "rescue enqueue order_id=%s" in rescue_source
    assert "_get_admin_language_code(admin_tg_id_int)" in admin_source
    assert "_build_rescue_admin_notification_text(order_id, language_code)" in admin_source
    assert "dedupe:fulfillment_rescue_admin" in admin_source


def test_fulfillment_locks_order_row_before_creating_gamedrops_order():
    source = function_source("_fulfill_order_via_gamedrops")
    assert "from app.models.models import MooGoldFulfillment, Order" in source
    assert "locked_order = db.execute(" in source
    assert "select(Order)" in source
    assert "Order.id == order_id" in source
    assert "with_for_update()" in source
    assert source.index("select(Order)") < source.index("create_gamedrops_order(")


def test_fulfillment_locks_existing_fulfillment_by_partner_order_id():
    source = function_source("_fulfill_order_via_gamedrops")
    partner_lookup = "select(MooGoldFulfillment)\n                    .where(MooGoldFulfillment.partner_order_id == transaction_id)\n                    .with_for_update()"
    assert partner_lookup in source
    assert source.index("existing = db.execute(") < source.index("create_gamedrops_order(")


def test_fulfillment_rechecks_idempotency_before_creating_gamedrops_order():
    source = function_source("_fulfill_order_via_gamedrops")
    assert "existing and existing.moogold_order_id" in source
    assert "existing.status in FINAL_FULFILLMENT_STATUSES" in source
    assert "order.status in FINAL_ORDER_STATUSES" in source
    assert "provider_status" in source
    assert source.index("existing and existing.moogold_order_id") < source.index("create_gamedrops_order(")


def test_admin_rescue_notification_is_localized_and_falls_back_to_ru():
    builder = function_source("_build_rescue_admin_notification_text")
    normalizer = function_source("_normalize_rescue_admin_lang")
    loader = function_source("_get_admin_language_code")
    admin = function_source("_send_rescue_admin_notification_once")
    assert "Авто-спасатель заказа" in builder
    assert "Order rescue" in builder
    assert "Buyurtma qutqarildi" in builder
    assert 'return "ru"' in normalizer
    assert "User.telegram_id == admin_tg_id" in loader
    assert "language_code = _get_admin_language_code(admin_tg_id_int)" in admin
    assert "Rescued paid order" not in builder


def test_fulfillment_rescue_max_age_setting_exists():
    assert "FULFILLMENT_RESCUE_MAX_AGE_SECONDS: int = 1800" in CONFIG_SOURCE


def test_historical_orders_are_never_enqueued_by_rescue_task():
    finder_source = function_source("_find_paid_orders_without_fulfillment")
    rescue_source = function_source("rescue_paid_orders_without_fulfillment")
    assert "Order.created_at >= oldest_allowed" in finder_source
    assert "_find_paid_orders_without_fulfillment(db, delay_seconds, max_age_seconds)" in rescue_source
    assert "fulfill_order_via_moogold.delay(order_id)" in rescue_source
    assert rescue_source.index("_find_paid_orders_without_fulfillment") < rescue_source.index("fulfill_order_via_moogold.delay(order_id)")


def test_docker_compose_passes_fulfillment_rescue_max_age_to_backend_worker_and_beat():
    lines = COMPOSE_SOURCE.splitlines()
    expected = "FULFILLMENT_RESCUE_MAX_AGE_SECONDS=${FULFILLMENT_RESCUE_MAX_AGE_SECONDS:-1800}"
    for service in ["backend", "celery_worker", "celery_beat"]:
        start = lines.index(f"  {service}:")
        end = next((idx for idx in range(start + 1, len(lines)) if lines[idx].startswith("  ") and not lines[idx].startswith("    ")), len(lines))
        block = "\n".join(lines[start:end])
        assert expected in block


def test_celery_beat_schedules_rescue_task():
    assert '"rescue-paid-orders-without-fulfillment"' in CELERY_SOURCE
    assert '"task": "app.services.moogold_fulfillment.rescue_paid_orders_without_fulfillment"' in CELERY_SOURCE
    assert '"schedule": 60.0' in CELERY_SOURCE


def test_docker_restarts_worker_beat_and_bot():
    lines = COMPOSE_SOURCE.splitlines()
    for service in ["bot", "celery_worker", "celery_beat"]:
        start = lines.index(f"  {service}:")
        end = next((idx for idx in range(start + 1, len(lines)) if lines[idx].startswith("  ") and not lines[idx].startswith("    ")), len(lines))
        block = "\n".join(lines[start:end])
        assert "restart: unless-stopped" in block


def test_rescue_tests_never_call_real_gamedrops_api():
    source = function_source("rescue_paid_orders_without_fulfillment")
    assert "create_gamedrops_order" not in source
    assert "GameDropsClient" not in source
