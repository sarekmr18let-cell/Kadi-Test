from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
FULFILLMENT_SOURCE = (ROOT / "backend/app/services/moogold_fulfillment.py").read_text()
CONFIG_SOURCE = (ROOT / "backend/app/core/config.py").read_text()
COMPOSE_SOURCE = (ROOT / "docker-compose.yml").read_text()
THIS_TEST_SOURCE = Path(__file__).read_text()


def function_source(name: str) -> str:
    tree = ast.parse(FULFILLMENT_SOURCE)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(FULFILLMENT_SOURCE, node) or ""
    raise AssertionError(f"function not found: {name}")


def test_multicopy_insufficient_balance_stops_after_first_provider_call_and_opens_circuit():
    source = function_source("_fulfill_order_via_gamedrops")
    provider_call = "response = create_gamedrops_order("
    insufficient_check = "if _is_insufficient_balance_error(exc):"

    assert "for copy_no in range(1, int(item.quantity or 1) + 1):" in source
    assert provider_call in source
    assert insufficient_check in source
    assert source.index("if _is_gamedrops_circuit_open():") < source.index(provider_call)
    assert "_open_gamedrops_circuit(\"insufficient_partner_balance\")" in source
    assert "_send_gamedrops_circuit_admin_notification_once(\"insufficient_partner_balance\")" in source
    assert "stop_provider_calls = True" in source
    assert "if stop_provider_calls:\n                        break" in source
    assert source.index(insufficient_check) < source.index("if stop_provider_calls:\n                        break")


def test_circuit_already_open_skips_gamedrops_create_order_entirely():
    source = function_source("_fulfill_order_via_gamedrops")
    initial_open_check = source.index("if _is_gamedrops_circuit_open():")
    provider_call = source.index("response = create_gamedrops_order(")

    assert initial_open_check < provider_call
    initial_block = source[initial_open_check:provider_call]
    assert "GameDrops circuit breaker is open" in initial_block
    assert "return {\"status\": \"skipped\", \"reason\": \"gamedrops_circuit_open\"" in initial_block


def test_rescue_task_skips_enqueue_when_gamedrops_circuit_is_open():
    source = function_source("rescue_paid_orders_without_fulfillment")
    circuit_check = source.index("if _is_gamedrops_circuit_open():")
    enqueue = source.index("fulfill_order_via_moogold.delay(order_id)")

    assert circuit_check < enqueue
    assert "reason\": \"gamedrops_circuit_open\"" in source
    assert "rescue skip order_id=%s reason=gamedrops_circuit_open" in source


def test_balance_guard_uses_default_12400_rate_and_warns_when_user_balance_exceeds_provider():
    source = function_source("check_gamedrops_balance_guard")

    assert "PROVIDER_BALANCE_USD_RATE: float = 12400.0" in CONFIG_SOURCE
    assert "user_balance_usd = user_balance_uzs / float(settings.PROVIDER_BALANCE_USD_RATE or 12400.0)" in source
    assert "if user_balance_usd > provider_balance_usd:" in source
    assert "user_balance_gt_provider_balance" in source
    assert "_send_gamedrops_balance_guard_admin_notification_once" in source


def test_no_real_gamedrops_api_calls_in_guard_tests():
    body = ast.get_source_segment(
        THIS_TEST_SOURCE,
        next(
            node
            for node in ast.parse(THIS_TEST_SOURCE).body
            if isinstance(node, ast.FunctionDef) and node.name == "test_no_real_gamedrops_api_calls_in_guard_tests"
        ),
    ) or ""
    forbidden = ["GameDrops" + "Client(", "create_" + "gamedrops_order(", "get_" + "balance(", "ht" + "tpx", "requ" + "ests"]
    for token in forbidden:
        assert token not in body


def test_docker_compose_passes_new_vars_to_backend_worker_and_beat():
    for var in [
        "GAMEDROPS_CIRCUIT_BREAKER_ENABLED",
        "GAMEDROPS_CIRCUIT_BREAKER_TTL_SECONDS",
        "GAMEDROPS_BALANCE_GUARD_ENABLED",
        "GAMEDROPS_BALANCE_GUARD_INTERVAL_SECONDS",
        "GAMEDROPS_BALANCE_WARNING_DEDUPE_TTL_SECONDS",
        "GAMEDROPS_MIN_BALANCE_USD",
        "PROVIDER_BALANCE_USD_RATE",
    ]:
        # Each variable appears as ${VAR:-default} in backend, celery_worker, and celery_beat.
        assert COMPOSE_SOURCE.count(f"${{{var}") == 3


def test_rescue_max_age_logic_from_pr42_remains_unchanged():
    source = function_source("_find_paid_orders_without_fulfillment")

    assert "FULFILLMENT_RESCUE_MAX_AGE_SECONDS: int = 1800" in CONFIG_SOURCE
    assert "oldest_allowed = now - timedelta(seconds=max_age_seconds)" in source
    assert "Order.created_at >= oldest_allowed" in source
