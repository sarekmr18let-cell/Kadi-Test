# GPT Fixes V9 — Product Requirements & Regions

This patch adds configurable account fields and region selection per product without changing the existing wallet/P2P/MooGold flow.

## Added

- Product-level requirements:
  - `target_type`: `game_id`, `telegram_username`, `none`
  - `requires_target_id`
  - `requires_server_id`
  - `requires_region`
  - custom labels for ID/server/region
  - configurable region options as JSON
  - optional help text
- Order-level target region storage:
  - `orders.target_region`
  - `orders.target_region_label`
- Alembic migration:
  - `005_product_requirements_regions.py`
- Frontend product page now shows only required fields for the selected product.
- Admin product modal can configure ID/server/region requirements and region options.
- Cart now stores account/region data from the product page.
- Backend validates required ID/server/region before deducting balance and creating the paid order.

## Important

For safety, orders that require account details are limited to one product/service type per cart.
This prevents a user from mixing MLBB and PUBG in one order with one target ID.

## Example region lines in admin

```text
uz_global=🇺🇿 UZB / 🌐 Global
uz_ph=🇺🇿 UZB / 🇵🇭 PH
ru=🇷🇺 RU
tr=🇹🇷 TR
id=🇮🇩 ID
```

## Existing flows preserved

- Wallet balance top-up
- P2P card lock
- HUMO Business parser
- MooGold fulfillment
- Test mode/diagnostics
