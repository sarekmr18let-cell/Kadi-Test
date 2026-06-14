# GPT Fixes v11 — KADI i18n RU/EN/UZ

## Added
- Mini App language switcher: RU / EN / UZ.
- `webapp/js/i18n.js` dictionary with Russian, English and Uzbek translations.
- Static UI translation through `data-i18n` attributes.
- Dynamic Mini App strings now use `tr(...)` for main customer flows: catalog, product page, cart, checkout, balance top-up, orders, profile and common admin labels.
- Telegram bot `/language` command and language selection inline keyboard.
- Bot opens Mini App with `?lang=ru|en|uz` so the Mini App follows the selected language.

## Kept untouched
- Payment logic, balance wallet, P2P card pool, HUMO parser, Telegram Business bridge, MooGold auto-fulfillment, product requirements/regions, database migrations and backend APIs.

## Brand
- Brand remains `KADI`.
- Tagline remains `TOP UP. PLAY MORE.`
