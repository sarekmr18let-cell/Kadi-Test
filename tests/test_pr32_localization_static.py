import ast
import re
from pathlib import Path
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def parse(path: str) -> ast.Module:
    return ast.parse(read(path), filename=path)


def find_function(module: ast.Module, name: str):
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


class PR32LocalizationStaticTests(unittest.TestCase):
    def test_single_users_language_patch_endpoint_and_profile_response(self):
        source = read("backend/app/api/users.py")
        self.assertEqual(source.count('@router.patch("/language"'), 1)
        self.assertNotIn("class LanguageUpdate", source)
        self.assertNotIn("from pydantic import BaseModel", source)
        module = ast.parse(source)
        endpoint = find_function(module, "update_language")
        endpoint_source = ast.get_source_segment(source, endpoint)
        self.assertIn("payload: UserLanguageUpdate", endpoint_source)
        self.assertIn("user.language_code = payload.language_code", endpoint_source)
        self.assertIn("return UserProfile(", endpoint_source)
        constants = [n.value for n in ast.walk(endpoint) if isinstance(n, ast.Constant)]
        self.assertIn("ru", read("backend/app/schemas/schemas.py"))
        self.assertIn("uz", read("backend/app/schemas/schemas.py"))
        self.assertIn("en", read("backend/app/schemas/schemas.py"))

    def test_profile_language_apply_does_not_call_plain_setlang(self):
        source = read("webapp/js/app.js")
        load_home = source[source.index("async function loadHomePage"):source.index("// ===== Catalog Page =====")]
        self.assertIn("applyLanguageFromProfile(languageProfile);", load_home)
        self.assertNotIn("setLang(languageProfile.language_code)", load_home)
        self.assertIn("if (state.pendingLanguageSave)", source)
        self.assertIn("source, silent: true", source)

    def test_manual_language_selection_still_patches_once_path(self):
        source = read("webapp/js/app.js")
        self.assertIn("if (event.detail?.source === 'user')", source)
        self.assertIn("saveSelectedLanguage(lang)", source)
        save_fn = source[source.index("async function saveSelectedLanguage"):source.index("async function flushPendingLanguageSave")]
        self.assertEqual(save_fn.count("api('PATCH', '/users/language'"), 1)
        self.assertIn("state.pendingLanguageSave", save_fn)
        self.assertIn("state.languageSaveInFlight", save_fn)

    def test_bot_backend_error_falls_back_to_confirmed_cache_or_ru(self):
        source = read("bot/main.py")
        self.assertIn("Short-lived cache of backend-confirmed language only", source)
        module = ast.parse(source)
        get_lang = ast.get_source_segment(source, find_function(module, "get_lang"))
        loader = ast.get_source_segment(source, find_function(module, "load_user_language"))
        self.assertNotIn("language_code", get_lang)
        self.assertIn('return "ru"', get_lang)
        self.assertIn("backend.get_profile", loader)
        self.assertIn("USER_LANGS[user.id] = lang", loader)
        self.assertIn('return USER_LANGS.get(user.id, "ru")', loader)
        self.assertNotIn("getattr(user, \"language_code\"", loader)

    def test_admin_completed_transition_queues_shared_task_once(self):
        source = read("backend/app/api/admin.py")
        module = ast.parse(source)
        endpoint = ast.get_source_segment(source, find_function(module, "update_order_status"))
        self.assertIn('if status_update.status == "completed" and previous_status != "completed":', endpoint)
        self.assertIn('_kadi_safe_celery_delay(send_order_notification, order.id, "completed")', endpoint)
        post_commit = endpoint[endpoint.index("await db.commit()") :]
        self.assertNotIn("_kadi_send_completed_direct_to_buyer", post_commit)
        self.assertNotIn("_kadi_order_notify_safe_no_celery(order.id", post_commit)

    def test_topup_notification_templates_ru_uz_en(self):
        source = read("backend/app/services/p2p.py")
        module = ast.parse(source)
        wanted = {"_kadi_format_uzs", "_kadi_normalize_language", "_kadi_notify_balance_topup"}
        ns = {"send_telegram_message_sync": lambda chat_id, message: sent.append((chat_id, message)), "logger": SimpleNamespace(info=lambda *a, **k: None)}
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                exec(compile(ast.Module([node], []), f"<{node.name}>", "exec"), ns)
        expected = {
            "ru": "✅ Баланс пополнен!\n\n💰 Сумма: 12 345 UZS\n💳 Ваш баланс: 67 890 UZS",
            "uz": "✅ Balans to‘ldirildi!\n\n💰 Summa: 12 345 UZS\n💳 Balansingiz: 67 890 UZS",
            "en": "✅ Balance topped up!\n\n💰 Amount: 12 345 UZS\n💳 Your balance: 67 890 UZS",
        }
        for lang, message in expected.items():
            sent = []
            ns["sent"] = sent
            ns["_kadi_notify_balance_topup"](SimpleNamespace(telegram_id=101, balance=67890, language_code=lang, id=1), 12345)
            self.assertEqual(sent, [(101, message)])

    def test_i18n_literal_tr_and_tor_keys_exist_in_all_languages(self):
        i18n = read("webapp/js/i18n.js")
        app = read("webapp/js/app.js")
        keys = set(re.findall(r"\b(?:tr|tOr)\(\s*['\"]([A-Za-z0-9_]+)['\"]", app))
        for key in ["dev_mode", "request_failed", "error", "failed_load_product", "payment_sent_for_check", "product_unavailable", "sending"]:
            self.assertIn(key, keys)
        for lang in ("ru", "en", "uz"):
            for key in keys:
                self.assertRegex(i18n, rf"\b{re.escape(key)}\s*:", msg=f"{key} missing for {lang}")


if __name__ == "__main__":
    unittest.main()
