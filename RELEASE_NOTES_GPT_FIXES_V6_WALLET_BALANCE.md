# GPT Fixes v6 — Wallet Balance + One Card Lock

This release changes the main payment flow from "pay each order directly" to a safer wallet flow.

## New main flow

1. User opens Profile.
2. User creates a balance top-up request.
3. Backend reserves one free P2P card from the admin card pool.
4. That card is locked to this one top-up until paid/cancelled/expired.
5. HUMO/Card bank notification is parsed via Telegram Business bridge.
6. Backend matches by card last4 + amount + active time window.
7. User balance is credited.
8. User buys products from balance.
9. Order is immediately marked paid and queued for MooGold auto-fulfillment.

## Backend changes

- Added `balance_topups` table.
- Added `matched_topup_id` and `matched_user_id` to `p2p_incoming_payments`.
- Added endpoints:
  - `POST /api/payments/topups`
  - `GET /api/payments/topups/active`
  - `GET /api/payments/topups/my`
  - `POST /api/payments/topups/{topup_id}/cancel`
  - `GET /api/admin/p2p/topups`
  - `POST /api/admin/p2p/topups/{topup_id}/review`
- Main `POST /api/orders` now pays from wallet balance.
- Order purchase creates a `Transaction(type="purchase")`.
- Balance top-up creates a `Transaction(type="topup")`.
- If incoming payment is late or amount mismatches, it goes to `needs_review` instead of auto-crediting.

## Frontend changes

- Profile now has a balance top-up form.
- Checkout now pays from balance.
- Admin P2P tab now shows cards and top-ups needing review.
- Prices and balance display as UZS.

## Safety notes

- One card is reserved for one active top-up only.
- Duplicate bank notifications are blocked via `external_id` hash.
- Outgoing/spending notifications are ignored.
- Mismatched/late payments are not credited automatically.
