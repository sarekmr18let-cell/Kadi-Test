# GPT Fixes V4 — MooGold Auto Fulfillment

Добавлена автоматическая отправка оплаченных заказов в MooGold.

## Что изменилось

- Добавлена таблица `moogold_fulfillments` для безопасной связи локального заказа/позиции с MooGold order id.
- После P2P автоподтверждения оплаты заказ автоматически ставится в очередь на MooGold.
- Если админ вручную ставит заказ в `paid`, он тоже автоматически отправляется в MooGold.
- Добавлен ручной endpoint: `POST /api/admin/orders/{order_id}/fulfill`.
- Webhook MooGold теперь обновляет конкретную fulfillment-запись и завершает локальный заказ только когда все позиции выполнены.
- Если у товара/вариации нет `moogold_variation_id`, заказ остаётся в `paid`, а админ получает уведомление `moogold_failed`.

## Важное условие

Для автоматической выдачи у каждой вариации товара должен быть заполнен `moogold_variation_id`. Это ID вариации из MooGold `product_detail`, а не локальный ID товара.

## Новые переменные `.env`

```env
MOOGOLD_AUTO_FULFILL_ENABLED=true
MOOGOLD_DEFAULT_ORDER_CATEGORY=1
```

`MOOGOLD_DEFAULT_ORDER_CATEGORY=1` — Direct Top Up. Для eVoucher используй `2`.
