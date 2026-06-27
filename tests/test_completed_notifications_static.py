import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/app/services/notifications.py").read_text()
MODULE = ast.parse(SOURCE)
HELPERS = {
    "escape_html",
    "_normalize_lang",
    "_as_tashkent_datetime",
    "_localized_completed_text",
    "_variation_product_name",
    "_variation_name",
    "_order_region",
    "_order_recipient",
    "build_completed_order_message",
    "build_completed_admin_message",
}


def load_helpers():
    ns = {}
    for node in MODULE.body:
        if isinstance(node, ast.FunctionDef) and node.name in HELPERS:
            exec(compile(ast.Module([node], []), f"<{node.name}>", "exec"), ns)
    return ns


def item(product_name="MLBB Diamonds", package_name="55 Diamonds", quantity=1):
    return SimpleNamespace(
        quantity=quantity,
        variation=SimpleNamespace(
            name=package_name,
            product=SimpleNamespace(name=product_name),
        ),
    )


def order(**overrides):
    base = dict(
        order_number="41",
        updated_at=datetime(2026, 6, 27, 9, 58),
        created_at=datetime(2026, 6, 26, 9, 0),
        target_region_label="🇺🇿 UZB / 🌐 Global",
        target_region=None,
        verified_target_name="DoraDura",
        target_id="12345",
        target_server="9876",
        items=[item()],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def user(lang="ru", username="admin", telegram_id=1001):
    return SimpleNamespace(language_code=lang, username=username, telegram_id=telegram_id)


class CompletedNotificationTemplateTests(unittest.TestCase):
    def setUp(self):
        self.helpers = load_helpers()

    def render(self, lang="ru", **order_overrides):
        return self.helpers["build_completed_order_message"](order(**order_overrides), user(lang=lang))

    def test_exact_ru_template(self):
        self.assertEqual(self.render("ru"), """✅ Заказ #41 доставлен!

📅 27.06.2026, 14:58
📂 MLBB Diamonds · 🇺🇿 UZB / 🌐 Global
📦 55 Diamonds
👤 DoraDura

Заказ выполнен.""")

    def test_exact_uz_template(self):
        self.assertEqual(self.render("uz"), """✅ Buyurtma #41 yetkazildi!

📅 27.06.2026, 14:58
📂 MLBB Diamonds · 🇺🇿 UZB / 🌐 Global
📦 55 Diamonds
👤 DoraDura

Buyurtma bajarildi.""")

    def test_exact_en_template(self):
        self.assertEqual(self.render("en"), """✅ Order #41 delivered!

📅 27.06.2026, 14:58
📂 MLBB Diamonds · 🇺🇿 UZB / 🌐 Global
📦 55 Diamonds
👤 DoraDura

Order completed.""")

    def test_utc_naive_to_tashkent_and_created_at_fallback(self):
        self.assertIn("📅 27.06.2026, 14:58", self.render("en"))
        fallback = self.render("en", updated_at=None, created_at=datetime(2026, 6, 27, 10, 1))
        self.assertIn("📅 27.06.2026, 15:01", fallback)

    def test_region_absent(self):
        rendered = self.render("en", target_region_label=None, target_region=None)
        self.assertIn("📂 MLBB Diamonds", rendered)
        self.assertNotIn("📂 MLBB Diamonds ·", rendered)

    def test_recipient_fallback(self):
        rendered = self.render("en", verified_target_name=None, target_id="12345", target_server="9876")
        self.assertIn("👤 12345 (9876)", rendered)

    def test_quantity_more_than_one(self):
        rendered = self.render("en", items=[item(quantity=2)])
        self.assertIn("📦 55 Diamonds ×2", rendered)

    def test_multiple_items(self):
        rendered = self.render("en", items=[item(package_name="55 Diamonds"), item(package_name="86 Diamonds")])
        self.assertIn("📦 55 Diamonds\n📦 86 Diamonds", rendered)

    def test_html_escaping(self):
        rendered = self.render(
            "en",
            order_number="<41&>",
            items=[item(product_name="MLBB <Diamonds>", package_name="55 & 5")],
            verified_target_name="Dora<Dura>&",
        )
        self.assertIn("#&lt;41&amp;&gt;", rendered)
        self.assertIn("MLBB &lt;Diamonds&gt;", rendered)
        self.assertIn("55 &amp; 5", rendered)
        self.assertIn("Dora&lt;Dura&gt;&amp;", rendered)

    def test_admin_shell_localized(self):
        build_admin = self.helpers["build_completed_admin_message"]
        base_message = "MESSAGE"
        self.assertTrue(build_admin(order(), user("ru"), base_message).startswith("🔔 Обновление заказа"))
        self.assertIn("Пользователь:", build_admin(order(), user("ru"), base_message))
        self.assertTrue(build_admin(order(), user("uz"), base_message).startswith("🔔 Buyurtma yangilanishi"))
        self.assertIn("Foydalanuvchi:", build_admin(order(), user("uz"), base_message))
        self.assertTrue(build_admin(order(), user("en"), base_message).startswith("🔔 Order Update"))
        self.assertIn("User:", build_admin(order(), user("en"), base_message))

    def test_non_completed_disabled_and_duplicate_marker_logic_present(self):
        task = next(node for node in ast.walk(MODULE) if isinstance(node, ast.FunctionDef) and node.name == "send_order_notification")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn('status != "completed"', source)
        self.assertIn('"status": "disabled"', source)
        self.assertIn('"status": "duplicate"', source)
        self.assertIn('marker_ttl_seconds = 90 * 24 * 60 * 60', source)
        lock_helper = next(node for node in ast.walk(MODULE) if isinstance(node, ast.FunctionDef) and node.name == '_completed_notification_lock')
        self.assertIn('timeout=120', ast.get_source_segment(SOURCE, lock_helper))

    def test_sender_returns_bool_and_no_real_messages_in_tests(self):
        sender = next(node for node in ast.walk(MODULE) if isinstance(node, ast.FunctionDef) and node.name == "send_telegram_message_sync")
        source = ast.get_source_segment(SOURCE, sender)
        self.assertIn("return True", source)
        self.assertIn("return False", source)


if __name__ == "__main__":
    unittest.main()
