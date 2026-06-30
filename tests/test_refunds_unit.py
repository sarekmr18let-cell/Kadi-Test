from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]


class FakeSelect:
    def where(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self


def fake_select(*args, **kwargs):
    return FakeSelect()


sqlalchemy = ModuleType("sqlalchemy")
sqlalchemy.select = fake_select
sys.modules["sqlalchemy"] = sqlalchemy


class Field:
    def __eq__(self, other):
        return True


class Model:
    id = Field()
    order_id = Field()
    user_id = Field()
    type = Field()
    status = Field()

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Order(Model):
    pass


class User(Model):
    pass


class Transaction(Model):
    pass


class MooGoldFulfillment(Model):
    pass


app_module = ModuleType("app")
models_pkg = ModuleType("app.models")
models_module = ModuleType("app.models.models")
models_module.MooGoldFulfillment = MooGoldFulfillment
models_module.Order = Order
models_module.Transaction = Transaction
models_module.User = User
sys.modules["app"] = app_module
sys.modules["app.models"] = models_pkg
sys.modules["app.models.models"] = models_module

spec = importlib.util.spec_from_file_location("refunds_under_test", ROOT / "backend/app/services/refunds.py")
refunds = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = refunds
spec.loader.exec_module(refunds)
refund_order_to_balance = refunds.refund_order_to_balance


class FakeResult:
    def __init__(self, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._scalars


class FakeDB:
    def __init__(self, order, user, fulfillments=None, existing_refund=None):
        self.order = order
        self.user = user
        self.fulfillments = fulfillments or []
        self.existing_refund = existing_refund
        self.added = []
        self.flushed = 0
        self.calls = 0

    def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return FakeResult(scalar=self.order)
        if self.calls == 2:
            return FakeResult(scalar=self.user)
        if self.calls == 3:
            return FakeResult(scalar=self.existing_refund)
        if self.calls == 4:
            return FakeResult(scalars=self.fulfillments)
        raise AssertionError(f"unexpected execute call {self.calls}")

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed += 1
        for idx, obj in enumerate(self.added, start=1):
            if getattr(obj, "id", None) is None:
                obj.id = idx


def make_order(status="failed", provider_status="failed", provider_response=None, total=30600):
    return Order(
        id=48,
        order_number="ORD-48",
        user_id=7,
        status=status,
        provider="gamedrops",
        provider_status=provider_status,
        provider_response=provider_response or {"message": "provider error"},
        total_amount=total,
        currency="UZS",
    )


def make_user(balance=1000):
    return User(id=7, telegram_id=10007, balance=balance)


def fulfillment(status):
    return SimpleNamespace(status=status)


def test_refund_order_to_balance_credits_user_and_creates_refund_transaction():
    order = make_order(status="refunded", provider_status="refunded")
    user = make_user(balance=400)
    db = FakeDB(order, user, fulfillments=[fulfillment("refunded")])

    result = refund_order_to_balance(db, order.id, "REFUND provider error")

    assert result.status == "refunded"
    assert user.balance == 31000
    assert len(db.added) == 1
    tx = db.added[0]
    assert tx.type == "refund"
    assert tx.status == "completed"
    assert tx.currency == "UZS"
    assert tx.amount == 30600
    assert tx.order_id == order.id


def test_second_call_or_existing_manual_refund_does_not_double_refund():
    order = make_order(status="refunded", provider_status="refunded")
    user = make_user(balance=400)
    existing_refund = Transaction(user_id=user.id, order_id=order.id, type="refund", amount=30600, currency="UZS", status="completed", description="manual refund")
    db = FakeDB(order, user, fulfillments=[fulfillment("refunded")], existing_refund=existing_refund)

    result = refund_order_to_balance(db, order.id, "REFUND provider error")

    assert result.status == "already_refunded"
    assert user.balance == 400
    assert db.added == []


def test_all_fulfillments_refunded_get_full_refund():
    order = make_order(status="processing", provider_status="refunded")
    user = make_user(balance=0)
    db = FakeDB(order, user, fulfillments=[fulfillment("refunded"), fulfillment("refunded")])

    result = refund_order_to_balance(db, order.id, "REFUND")

    assert result.status == "refunded"
    assert user.balance == 30600


def test_all_fulfillments_failed_get_full_refund_for_provider_error():
    order = make_order(status="failed", provider_status="failed")
    user = make_user(balance=10)
    db = FakeDB(order, user, fulfillments=[fulfillment("failed"), fulfillment("failed")])

    result = refund_order_to_balance(db, order.id, "WRONG_PRICE")

    assert result.status == "refunded"
    assert user.balance == 30610


def test_completed_plus_refunded_does_not_full_refund_and_marks_review():
    order = make_order(status="processing", provider_status="refunded")
    user = make_user(balance=10)
    db = FakeDB(order, user, fulfillments=[fulfillment("completed"), fulfillment("refunded")])

    result = refund_order_to_balance(db, order.id, "REFUND")

    assert result.status == "partial_provider_success_needs_review"
    assert user.balance == 10
    assert db.added == []
    assert order.provider_status == "needs_review"
    assert order.provider_response["refund_review_reason"] == "partial_provider_success_needs_review"
