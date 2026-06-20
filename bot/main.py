import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import WebAppInfo, MenuButtonWebApp
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from services.backend_client import BackendClient

# Configure logging
logging.basicConfig(level=logging.INFO)

# Get env vars
BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
ADMIN_TG_ID = os.getenv("ADMIN_TG_ID", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://tgbot.example.com")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "your_support")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@gameshop.com")
INTERNAL_BOT_SECRET = os.getenv("INTERNAL_BOT_SECRET", "")
P2P_WEBHOOK_SECRET = os.getenv("P2P_WEBHOOK_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")
if not INTERNAL_BOT_SECRET:
    logging.warning("INTERNAL_BOT_SECRET is not configured. Bot profile/orders/balance endpoints will be rejected by backend.")
if not P2P_WEBHOOK_SECRET:
    logging.warning("P2P_WEBHOOK_SECRET is not configured. Telegram Business P2P parser bridge will be rejected by backend.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
backend = BackendClient(BACKEND_URL)


LANGS = {"ru", "en", "uz"}
USER_LANGS: dict[int, str] = {}

BOT_TEXTS = {
    "ru": {
        "open_shop": "🛍️ Открыть магазин",
        "support": "📢 Поддержка",
        "support_short": "📞 Поддержка",
        "my_orders": "📦 Мои заказы",
        "balance": "💰 Баланс",
        "language": "🌐 Язык",
        "welcome": "🎮 <b>KADI</b>\n<i>TOP UP. PLAY MORE.</i>\n\nЗдесь можно купить:\n• Telegram Stars ⭐\n• Telegram Premium 💎\n• Донаты для игр 🎮\n• Подарочные карты 🎁\n\nНажми кнопку ниже, чтобы открыть магазин 👇",
        "menu_hint": "👋 Используй кнопки ниже или нажми <b>🛍️ Открыть магазин</b>.",
        "profile_title": "👤 <b>Профиль</b>",
        "orders_title": "📦 <b>Мои заказы</b>",
        "empty_orders": "📭 У тебя пока нет заказов.",
        "load_profile_error": "❌ Не удалось загрузить профиль. Попробуй ещё раз.",
        "load_orders_error": "❌ Не удалось загрузить заказы.",
        "load_balance_error": "❌ Не удалось загрузить баланс.",
        "support_text": "📞 <b>Поддержка</b>\n\nЕсли возникла проблема с заказом:\n1. Проверь статус в приложении\n2. Напиши @{support}\n3. Или на email: {email}\n\nРаботаем: 24/7",
        "select_language": "Выбери язык:",
        "language_saved": "✅ Язык изменён на русский.",
        "amount": "Сумма",
        "status": "Статус",
        "date": "Дата",
        "orders_count": "Заказы",
        "total_spent": "Потрачено",
        "referral_link": "Реферальная ссылка",
        "bank_sent": "✅ Уведомление банка отправлено в P2P parser.",
    },
    "en": {
        "open_shop": "🛍️ Open Shop", "support": "📢 Support", "support_short": "📞 Support", "my_orders": "📦 My Orders", "balance": "💰 Balance", "language": "🌐 Language",
        "welcome": "🎮 <b>KADI</b>\n<i>TOP UP. PLAY MORE.</i>\n\nYour one-stop shop for:\n• Telegram Stars ⭐\n• Telegram Premium 💎\n• Game top-ups 🎮\n• Gift cards 🎁\n\nTap the button below to open the shop 👇",
        "menu_hint": "👋 Use the buttons below or tap <b>🛍️ Open Shop</b>.",
        "profile_title": "👤 <b>Your Profile</b>", "orders_title": "📦 <b>Your Orders</b>", "empty_orders": "📭 You don't have any orders yet.",
        "load_profile_error": "❌ Error loading profile. Please try again.", "load_orders_error": "❌ Error loading orders.", "load_balance_error": "❌ Error loading balance.",
        "support_text": "📞 <b>Support</b>\n\nIf you have any issues with your order:\n1. Check your order status in the app\n2. Contact @{support}\n3. Or email: {email}\n\nWorking hours: 24/7",
        "select_language": "Choose language:", "language_saved": "✅ Language changed to English.", "amount": "Amount", "status": "Status", "date": "Date", "orders_count": "Orders", "total_spent": "Total Spent", "referral_link": "Referral Link", "bank_sent": "✅ Bank notification was sent to P2P parser.",
    },
    "uz": {
        "open_shop": "🛍️ Do‘konni ochish", "support": "📢 Yordam", "support_short": "📞 Yordam", "my_orders": "📦 Buyurtmalarim", "balance": "💰 Balans", "language": "🌐 Til",
        "welcome": "🎮 <b>KADI</b>\n<i>TOP UP. PLAY MORE.</i>\n\nBu yerda xarid qilishingiz mumkin:\n• Telegram Stars ⭐\n• Telegram Premium 💎\n• O‘yin donatlari 🎮\n• Sovg‘a kartalari 🎁\n\nDo‘konni ochish uchun pastdagi tugmani bosing 👇",
        "menu_hint": "👋 Pastdagi tugmalardan foydalaning yoki <b>🛍️ Do‘konni ochish</b> ni bosing.",
        "profile_title": "👤 <b>Profil</b>", "orders_title": "📦 <b>Buyurtmalarim</b>", "empty_orders": "📭 Hozircha buyurtmalaringiz yo‘q.",
        "load_profile_error": "❌ Profilni yuklab bo‘lmadi. Qayta urinib ko‘ring.", "load_orders_error": "❌ Buyurtmalarni yuklab bo‘lmadi.", "load_balance_error": "❌ Balansni yuklab bo‘lmadi.",
        "support_text": "📞 <b>Yordam</b>\n\nBuyurtma bo‘yicha muammo bo‘lsa:\n1. Ilovada statusni tekshiring\n2. @{support} ga yozing\n3. Yoki email: {email}\n\nIsh vaqti: 24/7",
        "select_language": "Tilni tanlang:", "language_saved": "✅ Til o‘zbekchaga o‘zgartirildi.", "amount": "Summa", "status": "Status", "date": "Sana", "orders_count": "Buyurtmalar", "total_spent": "Sarflangan", "referral_link": "Referal havola", "bank_sent": "✅ Bank xabari P2P parserga yuborildi.",
    },
}


def _normalize_lang(code: str | None) -> str:
    code = (code or "").lower()
    if code.startswith("ru"):
        return "ru"
    if code.startswith("uz"):
        return "uz"
    if code.startswith("en"):
        return "en"
    return "ru"


def get_lang(user: types.User | None) -> str:
    if user and user.id in USER_LANGS:
        return USER_LANGS[user.id]
    return _normalize_lang(getattr(user, "language_code", None))



def build_webapp_url(lang: str | None = None) -> str:
    """
    Build Mini App URL for Telegram.
    Adds cache-buster only if WEBAPP_URL does not already contain v=...
    """
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

    parts = urlsplit(WEBAPP_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    query.setdefault("v", "productux1")

    if lang:
        query["lang"] = lang

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

def bt(user: types.User | None, key: str, **kwargs) -> str:
    lang = get_lang(user)
    text = BOT_TEXTS.get(lang, BOT_TEXTS["ru"]).get(key) or BOT_TEXTS["ru"].get(key) or key
    return text.format(**kwargs)


def language_keyboard(user: types.User | None) -> types.InlineKeyboardMarkup:
    current = get_lang(user)
    def label(code: str, title: str) -> str:
        return ("✅ " if code == current else "") + title
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=label("ru", "Русский"), callback_data="lang:ru")],
        [types.InlineKeyboardButton(text=label("en", "English"), callback_data="lang:en")],
        [types.InlineKeyboardButton(text=label("uz", "O‘zbek"), callback_data="lang:uz")],
    ])

def _admin_ids() -> set[int]:
    ids = set()
    for raw in (ADMIN_TG_ID or "").replace(";", ",").split(","):
        raw = raw.strip()
        if raw.isdigit():
            ids.add(int(raw))
    return ids


def _looks_like_bank_notification(text: str) -> bool:
    text_upper = (text or "").upper()
    required_card_marker = "HUMOCARD" in text_upper or "UZCARD" in text_upper or "💳" in text_upper
    required_payment_marker = any(marker in text_upper for marker in ("ПОПОЛНЕНИЕ", "ОПЛАТА", "ОПЕРАЦИЯ", "➕", "➖"))
    return required_card_marker and required_payment_marker


async def _send_bank_notification_to_backend(message: types.Message, source: str) -> None:
    raw_text = message.text or message.caption or ""
    if not _looks_like_bank_notification(raw_text):
        return

    business_connection_id = getattr(message, "business_connection_id", None)
    external_id = f"{source}:{business_connection_id or 'direct'}:{message.chat.id}:{message.message_id}"

    try:
        result = await backend.send_p2p_incoming(
            raw_text=raw_text,
            source=source,
            external_id=external_id,
        )
        logging.info(
            "P2P bank notification sent to backend: status=%s amount=%s last4=%s matched_order=%s",
            result.get("status"),
            result.get("amount"),
            result.get("card_last4"),
            result.get("matched_order_id"),
        )
    except Exception as e:
        logging.exception("Failed to send P2P bank notification to backend: %s", e)


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Handle /start command - show welcome and WebApp button."""
    args = message.text.split()[1] if len(message.text.split()) > 1 else ""

    # Handle referral
    if args.startswith("ref_"):
        referrer_id = args.replace("ref_", "")
        try:
            await backend.register_referral(
                telegram_id=message.from_user.id,
                referrer_id=int(referrer_id)
            )
        except Exception as e:
            logging.warning(f"Referral registration failed: {e}")

    try:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(
                text=bt(message.from_user, "open_shop"),
                web_app=WebAppInfo(url=build_webapp_url(get_lang(message.from_user)))
            )
        )
    except Exception as e:
        logging.warning("Failed to set chat menu button: %s", e)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=bt(message.from_user, "open_shop"), web_app=WebAppInfo(url=build_webapp_url(get_lang(message.from_user))))],
            [types.InlineKeyboardButton(text=bt(message.from_user, "language"), callback_data="language")],
            [types.InlineKeyboardButton(text=bt(message.from_user, "support"), url=f"https://t.me/{SUPPORT_USERNAME}")]
        ]
    )
    await message.answer(bt(message.from_user, "welcome"), reply_markup=keyboard)


@dp.message(Command("language"))
async def cmd_language(message: types.Message):
    await message.answer(bt(message.from_user, "select_language"), reply_markup=language_keyboard(message.from_user))


@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    """Show user profile from backend."""
    try:
        profile = await backend.get_profile(message.from_user.id)
        text = f"""
{bt(message.from_user, 'profile_title')}

🆔 ID: <code>{profile['telegram_id']}</code>
👤 Username: @{profile.get('username', 'N/A')}
💰 {bt(message.from_user, 'balance')}: <b>{profile.get('balance', 0)} UZS</b>
📦 {bt(message.from_user, 'orders_count')}: {profile.get('orders_count', 0)}
💵 {bt(message.from_user, 'total_spent')}: {profile.get('total_spent', 0)} UZS

🔗 {bt(message.from_user, 'referral_link')}:
<code>{profile.get('referral_link', 'N/A')}</code>
        """.strip()
        await message.answer(text)
    except Exception as e:
        await message.answer(bt(message.from_user, "load_profile_error"))
        logging.error(f"Profile error: {e}")


@dp.message(Command("orders"))
async def cmd_orders(message: types.Message):
    """Show user's orders."""
    try:
        orders = await backend.get_orders(message.from_user.id)
        if not orders:
            await message.answer(bt(message.from_user, "empty_orders"))
            return
        text = bt(message.from_user, "orders_title") + "\n\n"
        for order in orders[:10]:
            status_emoji = {
                "created": "🆕", "awaiting_payment": "⏳", "paid": "✅", "processing": "🔄", "completed": "🎉", "cancelled": "❌", "refunded": "💰",
            }.get(order['status'], "📦")
            text += f"{status_emoji} <b>#{order['order_number']}</b>\n"
            text += f"   {bt(message.from_user, 'amount')}: {order['total_amount']} UZS\n"
            text += f"   {bt(message.from_user, 'status')}: {order['status']}\n"
            text += f"   {bt(message.from_user, 'date')}: {order['created_at'][:10]}\n\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(bt(message.from_user, "load_orders_error"))
        logging.error(f"Orders error: {e}")


@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    """Show user balance."""
    try:
        balance = await backend.get_balance(message.from_user.id)
        text = f"{bt(message.from_user, 'balance')}\n\n<b>{balance['balance']} {balance['currency']}</b>"
        await message.answer(text)
    except Exception as e:
        await message.answer(bt(message.from_user, "load_balance_error"))
        logging.error(f"Balance error: {e}")


@dp.message(Command("support"))
async def cmd_support(message: types.Message):
    """Show support info."""
    await message.answer(bt(message.from_user, "support_text", support=SUPPORT_USERNAME, email=SUPPORT_EMAIL))


# Telegram Business bridge: when @HUMOcardbot sends a notification to the linked
# business account, Telegram delivers it here as business_message.
if hasattr(dp, "business_message"):
    @dp.business_message(F.text)
    async def handle_business_bank_message(message: types.Message):
        await _send_bank_notification_to_backend(message, "telegram_business_humo")
else:
    logging.warning("Current aiogram version does not support business_message updates. Upgrade aiogram to >=3.13.")


@dp.message(lambda message: bool(
    message.text
    and message.from_user
    and message.from_user.id in _admin_ids()
    and _looks_like_bank_notification(message.text)
))
async def handle_admin_bank_notification_test(message: types.Message):
    """Manual fallback for testing: admin can paste a HUMO notification to the bot."""
    await _send_bank_notification_to_backend(message, "manual_admin_forward_humo")
    await message.answer(bt(message.from_user, "bank_sent"))


@dp.message()
async def handle_any_message(message: types.Message):
    """Handle any text message - show main menu."""
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=bt(message.from_user, "open_shop"),
                    web_app=WebAppInfo(url=build_webapp_url(get_lang(message.from_user)))
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=bt(message.from_user, "language"),
                    callback_data="language"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=bt(message.from_user, "my_orders"),
                    callback_data="orders"
                ),
                types.InlineKeyboardButton(
                    text=bt(message.from_user, "balance"),
                    callback_data="balance"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=bt(message.from_user, "support_short"),
                    url=f"https://t.me/{SUPPORT_USERNAME}"
                )
            ]
        ]
    )
    
    await message.answer(
        bt(message.from_user, "menu_hint"),
        reply_markup=keyboard
    )




@dp.callback_query(F.data == "language")
async def callback_language(callback: types.CallbackQuery):
    await callback.message.answer(bt(callback.from_user, "select_language"), reply_markup=language_keyboard(callback.from_user))
    await callback.answer()


@dp.callback_query(F.data.startswith("lang:"))
async def callback_set_language(callback: types.CallbackQuery):
    lang = callback.data.split(":", 1)[1]
    if lang not in LANGS:
        await callback.answer()
        return
    USER_LANGS[callback.from_user.id] = lang
    await callback.message.edit_text(bt(callback.from_user, "language_saved"), reply_markup=language_keyboard(callback.from_user))
    await callback.answer()


@dp.callback_query(F.data == "orders")
async def callback_orders(callback: types.CallbackQuery):
    """Show orders from inline button. Use callback.from_user, not callback.message.from_user."""
    try:
        orders = await backend.get_orders(callback.from_user.id)

        if not orders:
            await callback.message.answer(bt(callback.from_user, "empty_orders"))
            await callback.answer()
            return

        text = bt(callback.from_user, "orders_title") + "\n\n"
        for order in orders[:10]:
            status_emoji = {
                "created": "🆕",
                "awaiting_payment": "⏳",
                "paid": "✅",
                "processing": "🔄",
                "completed": "🎉",
                "cancelled": "❌",
                "refunded": "💰",
            }.get(order['status'], "📦")

            text += f"{status_emoji} <b>#{order['order_number']}</b>\n"
            text += f"   {bt(callback.from_user, 'amount')}: {order['total_amount']} UZS\n"
            text += f"   {bt(callback.from_user, 'status')}: {order['status']}\n"
            text += f"   {bt(callback.from_user, 'date')}: {order['created_at'][:10]}\n\n"

        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(bt(callback.from_user, "load_orders_error"))
        logging.error(f"Callback orders error: {e}")
    await callback.answer()


@dp.callback_query(F.data == "balance")
async def callback_balance(callback: types.CallbackQuery):
    """Show balance from inline button. Use callback.from_user, not callback.message.from_user."""
    try:
        balance = await backend.get_balance(callback.from_user.id)
        text = f"{bt(callback.from_user, 'balance')}\n\n<b>{balance['balance']} {balance['currency']}</b>"
        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(bt(callback.from_user, "load_balance_error"))
        logging.error(f"Callback balance error: {e}")
    await callback.answer()


async def main():
    await dp.start_polling(
        bot,
        skip_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":
    asyncio.run(main())
