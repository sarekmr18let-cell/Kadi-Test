# GPT Fixes V10 — KADI UI Redesign

Frontend-only visual redesign based on the approved KADI brand.

## Brand

- Brand: `KADI`
- Tagline: `TOP UP. PLAY MORE.`
- Style: dark gaming wallet, black background, gold/yellow accent.

## Changed

- Updated Mini App title/header branding from GameShop/KADITA-style names to KADI.
- Added balance pill in the header.
- Redesigned home screen: hero, quick actions, categories, large product catalog cards.
- Restyled catalog, product page, regions, variations, cart, wallet top-up, orders, profile, and admin cards using the same dark/gold visual language.
- Kept product requirements/regions logic from v9.
- Kept wallet, HUMO Business parser, P2P card pool, balance, MooGold, backend and database logic untouched.

## Not changed

- Backend payment logic
- Balance top-up logic
- HUMO parser
- Telegram Business bridge
- MooGold auto fulfillment
- Database migrations
- Product requirement fields
- Admin API

This patch intentionally focuses only on frontend UI/UX.
