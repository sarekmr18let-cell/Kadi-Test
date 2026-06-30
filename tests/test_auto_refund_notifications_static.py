import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/app/services/notifications.py").read_text()
MODULE = ast.parse(SOURCE)
HELPERS = {
    "escape_html",
    "_normalize_lang",
    "_format_uzs",
    "_localized_auto_refund_text",
    "build_auto_refund_message",
}


def load_helpers():
    ns = {}
    for node in MODULE.body:
        if isinstance(node, ast.FunctionDef) and node.name in HELPERS:
            exec(compile(ast.Module([node], []), f"<{node.name}>", "exec"), ns)
    return ns


def order(order_id=41):
    return SimpleNamespace(id=order_id)


def user(lang="ru"):
    return SimpleNamespace(language_code=lang)


class AutoRefundNotificationTemplateTests(unittest.TestCase):
    def setUp(self):
        self.helpers = load_helpers()

    def render(self, lang="ru", amount=125000):
        return self.helpers["build_auto_refund_message"](order(), user(lang), amount)

    def test_exact_ru_template(self):
        self.assertEqual(
            self.render("ru"),
            "Заказ #41 не был выполнен поставщиком. Деньги возвращены на ваш баланс: 125 000 UZS.",
        )

    def test_exact_uz_template(self):
        self.assertEqual(
            self.render("uz"),
            "Buyurtma #41 yetkazib beruvchi tomonidan bajarilmadi. Pul balansingizga qaytarildi: 125 000 UZS.",
        )

    def test_exact_en_template(self):
        self.assertEqual(
            self.render("en"),
            "Order #41 was not fulfilled by the provider. The money has been returned to your balance: 125 000 UZS.",
        )

    def test_unknown_language_falls_back_to_ru(self):
        self.assertEqual(self.render("de"), self.render("ru"))

    def test_send_auto_refund_uses_user_language_code_helper(self):
        task = next(node for node in ast.walk(MODULE) if isinstance(node, ast.FunctionDef) and node.name == "send_auto_refund_notification")
        source = ast.get_source_segment(SOURCE, task)
        self.assertIn("build_auto_refund_message(order, user, amount)", source)
        self.assertNotIn("Заказ #{order.id}", source)


if __name__ == "__main__":
    unittest.main()
