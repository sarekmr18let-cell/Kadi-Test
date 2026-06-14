# GPT Fixes V3 — HUMO Telegram Business P2P Parser

This release adds the first production-oriented bridge for automatic P2P payment parsing through Telegram Business and @HUMOcardbot-style messages.

## Added

- Telegram Business `business_message` handler in the bot.
- Backend client method for forwarding bank-bot notifications to `/api/payments/p2p/incoming`.
- Docker bot image now installs `aiogram>=3.13,<4.0` because Telegram Business updates require newer aiogram support.
- `P2P_WEBHOOK_SECRET` is now passed to the bot container.

## Improved P2P parser

The parser now supports HUMO format examples:

```text
🎉 Пополнение
➕ 440.000,00 UZS
📍 PAYME P2P UZCARD NA
💳 HUMOCARD *1828
🕓 14:07 13.06.2026
💰 440.118,07 UZS
```

Parsed result:

- amount: `440000.00`
- card_last4: `1828`
- direction: incoming/top-up

It also supports:

- `19.000,00 UZS` -> `19000.00`
- `3.467,00 UZS` -> `3467.00`
- `440,000.00 UZS` -> `440000.00`
- `21 736.00 UZS` -> `21736.00`

## Safety improvements

Outgoing messages are stored but ignored. These examples no longer risk matching an order:

```text
💸 Оплата
➖ 420.576,00 UZS
```

```text
💸 Операция
➖ 19.209,00 UZS
```

Only incoming notifications such as `Пополнение` / `➕` can mark an order as paid.

## How to use Telegram Business bridge

1. Add the bot as a Telegram Business chatbot.
2. Give it permission to read messages.
3. Make sure @HUMOcardbot notifications arrive in the connected business account.
4. Keep these env variables identical in backend and bot containers:

```env
INTERNAL_BOT_SECRET=your_internal_secret
P2P_WEBHOOK_SECRET=your_p2p_secret
```

## Test fallback

For testing, an admin from `ADMIN_TG_ID` can paste a HUMO notification directly into the bot. The bot will forward it to the backend parser.

Do not allow regular users to submit bank notifications directly.
