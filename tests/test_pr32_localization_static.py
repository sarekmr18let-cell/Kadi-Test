import ast
import json
import re
import subprocess
from pathlib import Path
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


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

    def test_user_action_handlers_reload_language_once_before_response(self):
        source = read("bot/main.py")
        module = ast.parse(source)
        expected = {
            "cmd_orders": "message.from_user",
            "cmd_balance": "message.from_user",
            "cmd_support": "message.from_user",
            "callback_orders": "callback.from_user",
            "callback_balance": "callback.from_user",
        }
        for function_name, user_expr in expected.items():
            handler = ast.get_source_segment(source, find_function(module, function_name))
            language_load = f"lang = await load_user_language({user_expr})"
            self.assertIn(language_load, handler, function_name)
            self.assertEqual(handler.count("load_user_language("), 1, function_name)
            response_positions = [
                pos for marker in ("message.answer", "callback.message.answer")
                if (pos := handler.find(marker)) != -1
            ]
            self.assertTrue(response_positions, function_name)
            self.assertLess(handler.index(language_load), min(response_positions), function_name)
            self.assertIn("bt_lang(lang,", handler, function_name)
            if function_name != "cmd_support":
                self.assertIn("_error", handler, function_name)

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
        sent = []
        ns = {
            "send_telegram_message_sync": lambda chat_id, message: sent.append((chat_id, message)),
            "logger": SimpleNamespace(info=lambda *a, **k: None),
        }
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                exec(compile(ast.Module([node], []), f"<{node.name}>", "exec"), ns)
        expected = {
            "ru": "✅ Баланс пополнен!\n\n💰 Сумма: 12 345 UZS\n💳 Ваш баланс: 67 890 UZS",
            "uz": "✅ Balans to‘ldirildi!\n\n💰 Summa: 12 345 UZS\n💳 Balansingiz: 67 890 UZS",
            "en": "✅ Balance topped up!\n\n💰 Amount: 12 345 UZS\n💳 Your balance: 67 890 UZS",
        }
        for lang, message in expected.items():
            sent.clear()
            ns["_kadi_notify_balance_topup"](SimpleNamespace(telegram_id=101, balance=67890, language_code=lang, id=1), 12345)
            self.assertEqual(sent, [(101, message)])

    def test_i18n_literal_tr_and_tor_keys_exist_in_all_languages(self):
        app = read("webapp/js/app.js")
        keys = set(re.findall(r"\b(?:tr|tOr)\(\s*['\"]([A-Za-z0-9_]+)['\"]", app))
        for key in ["dev_mode", "request_failed", "error", "failed_load_product", "payment_sent_for_check", "product_unavailable", "sending"]:
            self.assertIn(key, keys)

        script = r"""
const fs = require('fs');
const vm = require('vm');
const sandbox = {
  window: {},
  document: {
    documentElement: {},
    querySelectorAll: () => [],
    getElementById: () => null,
  },
  localStorage: {
    getItem: () => null,
    setItem: () => {},
  },
  CustomEvent: function CustomEvent() {},
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('webapp/js/i18n.js', 'utf8'), sandbox);
const dict = sandbox.window.I18N.dict;
const result = {};
for (const lang of ['ru', 'en', 'uz']) result[lang] = Object.keys(dict[lang]).sort();
process.stdout.write(JSON.stringify(result));
"""
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        dict_keys = {lang: set(values) for lang, values in json.loads(completed.stdout).items()}
        for key in keys:
            for lang in ("ru", "en", "uz"):
                self.assertIn(key, dict_keys[lang], f"{key} missing for {lang}")


class PR33OrderSuccessStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = read("webapp/js/app.js")
        cls.i18n = read("webapp/js/i18n.js")
        cls.css = read("webapp/css/style.css")
        cls.index = read("webapp/index.html")
        match = re.search(r"function showOrderConfirmation\(order\) \{(?P<body>.*?)\n\}\n\nfunction closeModal", cls.app, re.S)
        cls.assertIsNotNone(match, "showOrderConfirmation(order) not found")
        cls.confirmation = match.group("body")
        close_match = re.search(r"function closeModal\(\) \{(?P<body>.*?)\n\}", cls.app, re.S)
        cls.assertIsNotNone(close_match, "closeModal() not found")
        cls.close_modal = close_match.group("body")

    def test_paid_order_confirmation_removes_legacy_content(self):
        source = self.confirmation
        self.assertNotIn("🚀", source)
        self.assertNotIn("modal-close", source)
        self.assertNotIn("payment-instructions", source)
        self.assertNotIn("order_sent_to_admin_hint", source)
        self.assertNotIn("view_my_orders", source)

    def test_paid_order_confirmation_has_one_home_action(self):
        source = self.confirmation
        self.assertEqual(source.count("<button"), 1)
        self.assertIn('class="order-success-home"', source)
        self.assertIn('role', source)
        self.assertIn('dialog', source)
        self.assertIn('aria-modal', source)
        self.assertIn('true', source)
        self.assertIn("modal.setAttribute('aria-labelledby', 'order-success-title');", source)
        self.assertIn('id="order-success-title" class="order-success-title"', source)
        self.assertIn("tr('order_paid_number',", source)
        self.assertIn("number: escapeHtml(order.order_number)", source)
        self.assertIn("closeModal();", source)
        self.assertIn("navigateTo('home');", source)
        self.assertLess(source.index("closeModal();"), source.index("navigateTo('home');"))
        self.assertNotIn("navigateTo('orders')", source)
        self.assertIn("homeButton.focus();", source)


    def test_close_modal_removes_order_success_overlay(self):
        self.assertIn(".modal-overlay, .order-success-overlay", self.close_modal)
        self.assertIn("modal.remove()", self.close_modal)

    def test_paid_order_confirmation_i18n_keys_exist_for_all_languages(self):
        expected_values = [
            "order_paid_number: 'Заказ #{number} оплачен'",
            "order_processing_automatically: 'Обрабатывается автоматически'",
            "order_delivery_hint: 'Доставка обычно занимает несколько минут. После завершения придёт уведомление.'",
            "order_success_home: 'На главную'",
            "order_paid_number: 'Order #{number} paid'",
            "order_processing_automatically: 'Processing automatically'",
            "order_delivery_hint: 'Delivery usually takes a few minutes. You will receive a notification when it is completed.'",
            "order_success_home: 'Home'",
            "order_paid_number: 'Buyurtma #{number} to‘landi'",
            "order_processing_automatically: 'Avtomatik tarzda bajarilmoqda'",
            "order_delivery_hint: 'Yetkazib berish odatda bir necha daqiqa davom etadi. Yakunlanganda sizga xabar keladi.'",
            "order_success_home: 'Bosh sahifa'",
        ]
        for value in expected_values:
            self.assertIn(value, self.i18n)

        for key in (
            "order_paid_number",
            "order_processing_automatically",
            "order_delivery_hint",
            "order_success_home",
        ):
            self.assertEqual(self.i18n.count(key), 3, f"{key} must be defined once per RU/EN/UZ dictionary")

    def test_paid_order_confirmation_uses_scoped_css_classes(self):
        for class_name in (
            ".order-success-overlay",
            ".order-success-card",
            ".order-success-icon",
            ".order-success-title",
            ".order-success-amount",
            ".order-success-status",
            ".order-success-hint",
            ".order-success-home",
        ):
            self.assertIn(class_name, self.css)
        self.assertIn("width: calc(100% - 32px);", self.css)
        self.assertIn("env(safe-area-inset", self.css)

    def test_paid_order_confirmation_cache_busters_updated(self):
        self.assertIn("css/style.css?v=2026062717", self.index)
        self.assertIn("js/i18n.js?v=2026062717", self.index)
        self.assertIn("js/app.js?v=2026062717", self.index)


if __name__ == "__main__":
    unittest.main()
