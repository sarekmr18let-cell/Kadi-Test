import ast
from pathlib import Path
import sys
import types
import unittest
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/app/services/moogold_fulfillment.py").read_text()
MODULE = ast.parse(SOURCE)


def find_function(name: str) -> ast.AST:
    for node in ast.walk(MODULE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


class FakeLogger:
    def warning(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class FakeRedisLock:
    held = False
    owner = None
    next_owner = 1

    def __init__(self, timeout=None, **kwargs):
        self.timeout = timeout
        self.owner = None
        self.extend_calls = 0
        self.released = False
        self.fail_extend = False

    def acquire(self, blocking=False):
        if FakeRedisLock.held:
            return False
        FakeRedisLock.held = True
        self.owner = f"owner-{FakeRedisLock.next_owner}"
        FakeRedisLock.next_owner += 1
        FakeRedisLock.owner = self.owner
        return True

    def extend(self, ttl_seconds, replace_ttl=True):
        if self.fail_extend or FakeRedisLock.owner != self.owner:
            raise RuntimeError("lock lost")
        self.timeout = ttl_seconds
        self.extend_calls += 1
        return True

    def owned(self):
        return FakeRedisLock.owner == self.owner

    def release(self):
        if not self.owned():
            raise RuntimeError("cannot release another owner")
        FakeRedisLock.held = False
        FakeRedisLock.owner = None
        self.released = True


class FakeRedisClient:
    def __init__(self):
        self.locks = []

    def lock(self, *args, **kwargs):
        lock = FakeRedisLock(**kwargs)
        self.locks.append((args, kwargs, lock))
        return lock


def load_helper_functions():
    ns = {"Any": Any, "Optional": Optional}
    for node in MODULE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "GAMEDROPS_STATUS_MAP":
                    exec(compile(ast.Module([node], []), "<gamedrops-status-map>", "exec"), ns)
        if isinstance(node, ast.FunctionDef) and node.name in {"_map_gamedrops_status", "_extract_gamedrops_status"}:
            exec(compile(ast.Module([node], []), f"<{node.name}>", "exec"), ns)
    return ns["_map_gamedrops_status"], ns["_extract_gamedrops_status"]


def load_lock_helpers(fake_client=None):
    fake_client = fake_client or FakeRedisClient()
    fake_redis_module = types.ModuleType("redis")
    fake_redis_module.Redis = types.SimpleNamespace(from_url=lambda url: fake_client)
    sys.modules["redis"] = fake_redis_module
    ns = {
        "settings": types.SimpleNamespace(REDIS_URL="redis://fake/0"),
        "logger": FakeLogger(),
    }
    for node in MODULE.body:
        if isinstance(node, ast.ClassDef) and node.name == "_GameDropsStatusSyncLock":
            exec(compile(ast.Module([node], []), "<lock-class>", "exec"), ns)
        if isinstance(node, ast.FunctionDef) and node.name == "_acquire_gamedrops_status_sync_lock":
            exec(compile(ast.Module([node], []), "<acquire-lock>", "exec"), ns)
    return ns["_GameDropsStatusSyncLock"], ns["_acquire_gamedrops_status_sync_lock"], fake_client


class GameDropsStatusSyncStaticTests(unittest.TestCase):
    def test_processing_stays_processing(self):
        map_status, _ = load_helper_functions()
        self.assertEqual(map_status("PROCESSING"), "processing")
        self.assertEqual(map_status("SUBMITTED"), "processing")

    def test_completed_and_terminal_status_mapping(self):
        map_status, _ = load_helper_functions()
        self.assertEqual(map_status("COMPLETED"), "completed")
        self.assertEqual(map_status("CANCELED"), "cancelled")
        self.assertEqual(map_status("FAILED"), "failed")
        self.assertEqual(map_status("REFUND"), "refunded")
        self.assertEqual(map_status("REFUNDED"), "refunded")

    def test_unknown_status_does_not_complete(self):
        map_status, _ = load_helper_functions()
        self.assertIsNone(map_status("WAITING_FOR_VENDOR"))

    def test_status_can_be_top_level_or_nested_data(self):
        _, extract_status = load_helper_functions()
        self.assertEqual(extract_status({"orderStatus": "COMPLETED"}), "COMPLETED")
        self.assertEqual(extract_status({"data": {"status": "PROCESSING"}}), "PROCESSING")

    def test_sync_task_filters_order_id_and_limits_batch(self):
        task = find_function("sync_gamedrops_order_statuses")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn("limit(100)", source)
        self.assertIn("if order_id is not None", source)
        self.assertIn("MooGoldFulfillment.order_id == int(order_id)", source)

    def test_sync_task_handles_errors_per_fulfillment(self):
        task = find_function("sync_gamedrops_order_statuses")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn("for fulfillment in fulfillments", source)
        self.assertIn("except Exception as exc", source)
        self.assertIn("db.rollback()", source)
        self.assertIn("errors += 1", source)

    def test_completed_notification_is_sent_once_after_commit(self):
        task = find_function("sync_gamedrops_order_statuses")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn('previous_order_status != "completed"', source)
        self.assertIn('final_order_status == "completed"', source)
        self.assertIn("db.commit()", source)
        self.assertLess(source.index("db.commit()"), source.index("send_order_notification.delay"))
        self.assertIn('send_order_notification.delay(notify_order_id, "completed")', source)
        self.assertNotIn('send_order_notification.delay(notify_order_id, "processing")', source)


    def test_second_worker_does_not_get_occupied_lock(self):
        FakeRedisLock.held = False
        FakeRedisLock.owner = None
        _, acquire_lock, _ = load_lock_helpers()
        first = acquire_lock()
        second = acquire_lock()
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        first.release()

    def test_lock_ttl_is_at_least_120_and_extends_with_owner(self):
        FakeRedisLock.held = False
        FakeRedisLock.owner = None
        _, acquire_lock, fake_client = load_lock_helpers()
        acquired = acquire_lock()
        self.assertIsNotNone(acquired)
        args, kwargs, fake_lock = fake_client.locks[0]
        self.assertGreaterEqual(kwargs["timeout"], 120)
        self.assertTrue(acquired.extend())
        self.assertEqual(fake_lock.extend_calls, 1)
        acquired.release()

    def test_release_does_not_delete_another_owner_lock(self):
        FakeRedisLock.held = False
        FakeRedisLock.owner = None
        _, acquire_lock, fake_client = load_lock_helpers()
        acquired = acquire_lock()
        fake_lock = fake_client.locks[0][2]
        FakeRedisLock.owner = "other-owner"
        acquired.release()
        self.assertFalse(fake_lock.released)

    def test_lock_loss_stops_before_db_write(self):
        task = find_function("sync_gamedrops_order_statuses")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn('"status": "lock_lost"', source)
        self.assertLess(source.index("not status_lock.extend() or not status_lock.owned()"), source.index("fulfillment.response_payload"))

    def test_status_sync_never_calls_create_order(self):
        task = find_function("sync_gamedrops_order_statuses")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn("_get_gamedrops_order_status", source)
        self.assertNotIn("create_gamedrops_order", source)
        self.assertNotIn("create_order(", source)


if __name__ == "__main__":
    unittest.main()
