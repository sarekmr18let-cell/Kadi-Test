import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def parse(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(), filename=path)


def find_function(module: ast.Module, name: str) -> ast.AST:
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


class LanguageSyncStaticTests(unittest.TestCase):
    def test_bot_language_selection_uses_internal_patch(self):
        client_module = parse("bot/services/backend_client.py")
        method = find_function(client_module, "save_language")
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        request_calls = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "_request"]
        self.assertTrue(request_calls, "BackendClient.save_language must call _request")
        constants = [node.value for node in ast.walk(method) if isinstance(node, ast.Constant)]
        self.assertIn("PATCH", constants)
        source = ast.get_source_segment((ROOT / "bot/services/backend_client.py").read_text(), method)
        self.assertIn("api/bot/profile/", source)
        self.assertIn("/language", source)

    def test_bot_callback_saves_before_success_cache_update(self):
        bot_module = parse("bot/main.py")
        callback = find_function(bot_module, "callback_set_language")
        names = [node.id for node in ast.walk(callback) if isinstance(node, ast.Name)]
        self.assertIn("save_user_language", names)
        self.assertIn("saved_lang", names)
        self.assertIn("language_save_failed", [node.value for node in ast.walk(callback) if isinstance(node, ast.Constant)])
        source = ast.get_source_segment((ROOT / "bot/main.py").read_text(), callback)
        self.assertLess(source.index("save_user_language"), source.index("language_saved"))

    def test_start_reloads_language_from_backend_cache_source(self):
        bot_module = parse("bot/main.py")
        start = find_function(bot_module, "cmd_start")
        source = ast.get_source_segment((ROOT / "bot/main.py").read_text(), start)
        self.assertIn("load_user_language(message.from_user)", source)
        self.assertIn("build_webapp_url(lang)", source)
        loader = find_function(bot_module, "load_user_language")
        loader_source = ast.get_source_segment((ROOT / "bot/main.py").read_text(), loader)
        self.assertIn("backend.get_profile", loader_source)
        self.assertIn("USER_LANGS[user.id] = lang", loader_source)

    def test_internal_endpoint_is_protected_and_validates_language(self):
        module = parse("backend/app/api/bot_internal.py")
        endpoint = find_function(module, "update_language_for_bot")
        endpoint_source = ast.get_source_segment((ROOT / "backend/app/api/bot_internal.py").read_text(), endpoint)
        self.assertIn("telegram_id", endpoint_source)
        self.assertIn("language_code", endpoint_source)
        self.assertIn("db.commit", endpoint_source)
        constants = [node.value for node in ast.walk(module) if isinstance(node, ast.Constant)]
        self.assertIn("/profile/{telegram_id}/language", constants)
        self.assertIn("X-Bot-Secret", constants)
        self.assertIn("ru", constants)
        self.assertIn("uz", constants)
        self.assertIn("en", constants)
        self.assertIn("language_code must be one of: ru, uz, en", constants)

    def test_internal_endpoint_creates_missing_user_without_duplicate_path(self):
        module = parse("backend/app/api/bot_internal.py")
        endpoint = find_function(module, "update_language_for_bot")
        source = ast.get_source_segment((ROOT / "backend/app/api/bot_internal.py").read_text(), endpoint)
        self.assertIn("select(User).where(User.telegram_id == telegram_id)", source)
        self.assertIn("if not user:", source)
        self.assertIn("User(", source)
        self.assertIn("referral_code=f\"REF{telegram_id}\"", source)
        self.assertIn("else:", source)


if __name__ == "__main__":
    unittest.main()
