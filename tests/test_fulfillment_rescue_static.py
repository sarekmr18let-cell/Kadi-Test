import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULFILLMENT_SOURCE = (ROOT / "backend/app/services/moogold_fulfillment.py").read_text()
CELERY_SOURCE = (ROOT / "backend/app/celery_app.py").read_text()
COMPOSE_SOURCE = (ROOT / "docker-compose.yml").read_text()
MODULE = ast.parse(FULFILLMENT_SOURCE)


def function_source(name: str) -> str:
    for node in ast.walk(MODULE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(FULFILLMENT_SOURCE, node)
    raise AssertionError(f"function {name} not found")


def test_rescue_query_selects_old_paid_gamedrops_orders_without_fulfillment():
    source = function_source("_find_paid_orders_without_fulfillment")
    assert 'Order.status == "paid"' in source
    assert "Order.created_at <= cutoff" in source
    assert "ProductVariation.provider" in source
    assert "Product.provider" in source
    assert '"gamedrops"' in source
    assert "MooGoldFulfillment.id == None" in source


def test_rescue_query_skips_delivered_refunded_cancelled_failed_provider_statuses():
    source = function_source("_find_paid_orders_without_fulfillment")
    assert "FINAL_PROVIDER_STATUSES" in source
    assert "func.lower(Order.provider_status).notin_" in source
    for status in ["delivered", "refunded", "cancelled", "failed"]:
        assert status in FULFILLMENT_SOURCE


def test_rescue_query_skips_existing_provider_order_id_and_final_fulfillments():
    source = function_source("_find_paid_orders_without_fulfillment")
    assert "MooGoldFulfillment.moogold_order_id == None" in source
    assert 'MooGoldFulfillment.moogold_order_id == ""' in source
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
    assert "rescued_paid_orders_without_fulfillment checked=%s rescued=%s skipped=%s" in rescue_source
    assert "rescue enqueue order_id=%s" in rescue_source
    assert "Rescued paid order" in admin_source
    assert "dedupe:fulfillment_rescue_admin" in admin_source


def test_fulfillment_rechecks_idempotency_before_creating_gamedrops_order():
    source = function_source("_fulfill_order_via_gamedrops")
    assert "with_for_update()" in source
    assert "existing and existing.moogold_order_id" in source
    assert "existing.status in FINAL_FULFILLMENT_STATUSES" in source
    assert "order.status in FINAL_ORDER_STATUSES" in source
    assert "provider_status" in source
    assert source.index("existing and existing.moogold_order_id") < source.index("create_gamedrops_order(")


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
