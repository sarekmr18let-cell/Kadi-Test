# GPT Fixes v7 — Test Mode & Diagnostics

This package is focused on safe testing and diagnostics before running real money flows.

## Added

### Admin System Check
New admin endpoints:

- `GET /api/admin/system/check`
- `POST /api/admin/system/p2p/parse-test`
- `POST /api/admin/system/p2p/process-test`

The system check validates:

- PostgreSQL connection
- Redis connection
- JWT secret length
- bot token presence
- internal bot secret
- P2P webhook secret
- HTTPS WebApp URL
- MooGold credentials or test mode
- active P2P cards
- active products and variations
- missing `moogold_variation_id`
- top-ups that need review
- failed MooGold fulfillments

### Mini App Admin UI
Added a new admin tab:

- `Admin Panel → System Check`

It can:

- run system readiness checks
- parse a HUMO/CardXabar message without changing balances
- process a test payment only when `P2P_TEST_MODE=true`

### MooGold Test Mode
New env variable:

```env
MOOGOLD_TEST_MODE=false
```

When set to `true`, MooGold fulfillment returns fake `TEST-*` order IDs and never sends real requests to MooGold.

### P2P Test Mode
New env variable:

```env
P2P_TEST_MODE=false
```

When set to `true`, admins can run `/api/admin/system/p2p/process-test` from the Mini App to test matching a HUMO notification against a pending top-up.

### Wallet/P2P Safety Settings
New env variables:

```env
P2P_PAYMENT_TTL_MINUTES=5
WALLET_TOPUP_MIN_AMOUNT=1000
WALLET_TOPUP_MAX_AMOUNT=5000000
```

## Important

`parse-test` is always safe and does not change balances.

`process-test` can credit a pending top-up, so it requires:

```env
P2P_TEST_MODE=true
```

Do not enable test mode permanently in production.
