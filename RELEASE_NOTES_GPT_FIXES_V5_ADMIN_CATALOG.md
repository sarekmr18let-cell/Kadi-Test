# GPT Fixes V5 — Admin Catalog + MooGold Control

This package keeps all previous fixes and adds the missing admin workflow needed to run the shop from a phone.

## What changed

### 1. Fixed broken admin dashboard IDs
The Mini App had duplicate HTML ids such as `admin-users` for both dashboard stats and the Users tab content.
That could break admin tab switching and dashboard updates.

Fixed ids:
- `admin-stat-users`
- `admin-stat-orders`
- `admin-stat-revenue`
- `admin-stat-pending`

### 2. Added real product management UI
Admin Panel → Products now supports:
- add category
- add product
- edit product
- disable product
- add variation
- edit variation
- disable variation

### 3. Added MooGold mapping fields in the UI
You can now fill:
- product MooGold ID
- variation MooGold ID

This is important because auto-delivery needs `moogold_variation_id` for each sellable package.

Example:
- Mobile Legends → product MooGold ID
- 86 Diamonds → variation MooGold ID
- 172 Diamonds → variation MooGold ID

### 4. Added manual MooGold resend button
Admin Orders now has a `Send MooGold` button for paid/processing orders.
Use it if:
- payment was approved manually
- first MooGold attempt failed
- you fixed missing MooGold variation IDs and want to retry

### 5. Product API schema now exposes `moogold_id`
`ProductResponse` now includes `moogold_id`, so the frontend can show and edit MooGold product mapping.

## No database migration required
This release only uses fields and endpoints already added in previous packages.

## Recommended next check
After deploying:
1. Open Mini App.
2. Go to Profile → Admin Panel → Products.
3. Add a category.
4. Add a product.
5. Add one variation with `moogold_variation_id`.
6. Create a test order.
7. Confirm P2P payment test.
8. Check that MooGold fulfillment is queued.
