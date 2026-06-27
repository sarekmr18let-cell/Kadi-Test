import ast
from pathlib import Path
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

    def test_status_sync_never_calls_create_order(self):
        task = find_function("sync_gamedrops_order_statuses")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn("_get_gamedrops_order_status", source)
        self.assertNotIn("create_gamedrops_order", source)
        self.assertNotIn("create_order(", source)


if __name__ == "__main__":
    unittest.main()
