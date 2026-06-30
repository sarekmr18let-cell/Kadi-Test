import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _install_import_stubs():
    fastapi = types.ModuleType("fastapi")
    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
    fastapi.HTTPException = HTTPException
    fastapi.status = SimpleNamespace(HTTP_400_BAD_REQUEST=400)
    sys.modules.setdefault("fastapi", fastapi)

    sqlalchemy = types.ModuleType("sqlalchemy")
    sqlalchemy.select = lambda *args, **kwargs: SimpleNamespace(where=lambda *a, **k: SimpleNamespace(subquery=lambda: None))
    sqlalchemy.func = SimpleNamespace(coalesce=lambda *a, **k: None, sum=lambda *a, **k: None)
    sqlalchemy.or_ = lambda *args, **kwargs: None
    sys.modules.setdefault("sqlalchemy", sqlalchemy)
    sqlalchemy_ext = types.ModuleType("sqlalchemy.ext")
    sqlalchemy_asyncio = types.ModuleType("sqlalchemy.ext.asyncio")
    sqlalchemy_asyncio.AsyncSession = object
    sys.modules.setdefault("sqlalchemy.ext", sqlalchemy_ext)
    sys.modules.setdefault("sqlalchemy.ext.asyncio", sqlalchemy_asyncio)
    sqlalchemy_orm = types.ModuleType("sqlalchemy.orm")
    sqlalchemy_orm.selectinload = lambda *args, **kwargs: None
    sys.modules.setdefault("sqlalchemy.orm", sqlalchemy_orm)

    config = types.ModuleType("app.core.config")
    config.settings = SimpleNamespace(P2P_PAYMENT_TTL_MINUTES=5, WALLET_TOPUP_MIN_AMOUNT=0, WALLET_TOPUP_MAX_AMOUNT=None)
    sys.modules.setdefault("app.core.config", config)
    notifications = types.ModuleType("app.services.notifications")
    notifications.send_order_notification = lambda *args, **kwargs: None
    notifications.send_telegram_message_sync = lambda *args, **kwargs: None
    sys.modules.setdefault("app.services.notifications", notifications)

    models = types.ModuleType("app.models.models")
    for name in ["User", "Order", "PromoCode", "Transaction", "P2PCard", "P2PPaymentSession", "P2PIncomingPayment", "BalanceTopUp"]:
        setattr(models, name, type(name, (), {}))
    sys.modules.setdefault("app.models.models", models)


_install_import_stubs()
p2p = importlib.import_module("app.services.p2p")


def card(card_id, sort_order=0, min_amount=0, max_amount=None):
    return SimpleNamespace(id=card_id, sort_order=sort_order, min_amount=min_amount, max_amount=max_amount, is_active=True)


def choose(rows):
    return p2p._pick_lowest_load_card(rows)


def test_three_free_cards_pick_lowest_today_paid_amount():
    cards = [card(1), card(2), card(3)]
    assert choose([(cards[0], 100000, 100000), (cards[1], 500000, 500000), (cards[2], 10000, 10000)]).id == 3


def test_ten_cards_pick_minimum_load_across_all_cards():
    cards = [card(i, sort_order=i) for i in range(1, 11)]
    loads = [(c, 100000 + c.id, 100000 + c.id) for c in cards]
    loads[-1] = (cards[-1], 1, 1)
    assert choose(loads).id == 10


def test_pending_amount_is_part_of_today_load():
    cards = [card(1), card(2)]
    # Card 1 has lower paid amount but its active pending amount makes total load higher.
    assert choose([(cards[0], 250000, 100000), (cards[1], 200000, 200000)]).id == 2


def test_today_load_tie_uses_lifetime_paid_amount():
    cards = [card(1), card(2)]
    assert choose([(cards[0], 100000, 900000), (cards[1], 100000, 200000)]).id == 2


def test_today_and_lifetime_tie_uses_sort_order_then_id():
    assert choose([(card(3, 20), 100, 1000), (card(2, 10), 100, 1000), (card(1, 10), 100, 1000)]).id == 1


def test_tashkent_today_bounds_are_utc_naive():
    start, end = p2p._today_tashkent_utc_naive_bounds(datetime(2026, 6, 30, 20, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 6, 30, 19, 0)
    assert end == datetime(2026, 7, 1, 19, 0)
    assert start.tzinfo is None and end.tzinfo is None


def test_daily_limit_is_not_used_by_new_logic():
    source = (ROOT / "backend/app/services/p2p.py").read_text(encoding="utf-8")
    pick_source = source[source.index("async def pick_free_card"):source.index("async def generate_unique_amount")]
    assert "daily_limit" not in pick_source


def test_min_amount_max_amount_predicates_remain_in_pick_free_card():
    source = (ROOT / "backend/app/services/p2p.py").read_text(encoding="utf-8")
    pick_source = source[source.index("async def pick_free_card"):source.index("async def generate_unique_amount")]
    assert "P2PCard.min_amount <= amount" in pick_source
    assert "P2PCard.max_amount >= amount" in pick_source


def test_blockers_remain_excluded_in_pick_free_card():
    source = (ROOT / "backend/app/services/p2p.py").read_text(encoding="utf-8")
    pick_source = source[source.index("async def pick_free_card"):source.index("async def generate_unique_amount")]
    assert "P2PPaymentSession.status == \"active\"" in pick_source
    assert "BalanceTopUp.status == \"pending\"" in pick_source
    assert "BalanceTopUp.status == \"needs_review\"" in pick_source


def test_no_available_card_error_detail_is_clear():
    source = (ROOT / "backend/app/services/p2p.py").read_text(encoding="utf-8")
    assert "No free P2P card is available for this amount" in source
    assert "HTTP_400_BAD_REQUEST" in source


def test_create_balance_topup_uses_pick_free_card_and_pending_status():
    source = (ROOT / "backend/app/services/p2p.py").read_text(encoding="utf-8")
    create_source = source[source.index("async def create_balance_topup"):source.index("async def count_promo_usage_if_needed")]
    assert "card = await pick_free_card(db, amount)" in create_source
    assert "status=\"pending\"" in create_source
    assert "card_id=card.id" in create_source


def test_pick_free_card_queries_all_available_cards_before_fair_selection():
    source = (ROOT / "backend/app/services/p2p.py").read_text(encoding="utf-8")
    pick_source = source[source.index("async def pick_free_card"):source.index("async def generate_unique_amount")]
    assert "available_cards = result.scalars().all()" in pick_source
    assert "_pick_lowest_load_card" in pick_source
