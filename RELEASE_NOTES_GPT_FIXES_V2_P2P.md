# GPT Fixes V2 — P2P Payment Foundation

## Что добавлено

### 1. Пул карт P2P
Админ может добавлять карты без изменения кода:

- номер карты
- владелец
- банк
- платежная система: Humo / Uzcard / Visa / Other
- минимальная сумма
- максимальная сумма
- активна / выключена

API:

```text
GET    /api/admin/p2p/cards
POST   /api/admin/p2p/cards
PUT    /api/admin/p2p/cards/{card_id}
DELETE /api/admin/p2p/cards/{card_id}
```

Mini App Admin Panel получил вкладку **P2P Cards**.

---

### 2. Выдача свободной карты пользователю
Для заказа создается P2P session:

```text
POST /api/payments/p2p/session/{order_id}
GET  /api/payments/p2p/session/{order_id}
```

Сессия содержит:

- свободную карту из пула
- точную уникальную сумму
- время истечения
- статус active / paid / expired / cancelled

По умолчанию окно оплаты: **5 минут**.

---

### 3. Уникальная сумма для автопоиска платежа
К сумме заказа добавляется случайный хвост:

```text
base_amount + 1..499 UZS
```

Например:

```text
220000 → 220118 UZS
```

Это нужно, чтобы банк-уведомление можно было точно сопоставить с заказом.

---

### 4. Внутренний webhook для банк-бота / Telegram Business bridge
Добавлен endpoint:

```text
POST /api/payments/p2p/incoming
Header: X-P2P-Secret: <P2P_WEBHOOK_SECRET>
```

Payload:

```json
{
  "source": "CardXabarBot",
  "raw_text": "Пополнение ➕ 220,118.00 UZS ... HUMOCARD *1234 ...",
  "amount": null,
  "card_last4": null,
  "external_id": null
}
```

Backend сам пытается достать:

- сумму
- последние 4 цифры карты
- дату/время платежа

Если находит активную payment session с такой же уникальной суммой — заказ становится `paid`.

---

### 5. Новые таблицы БД
Добавлена миграция:

```text
backend/alembic/versions/002_p2p_card_pool.py
```

Новые таблицы:

- `p2p_cards`
- `p2p_payment_sessions`
- `p2p_incoming_payments`

В `orders` добавлено поле:

- `promo_usage_counted`

---

## Что нужно добавить в .env

```env
P2P_WEBHOOK_SECRET=generate_another_random_string_32_chars_min
```

---

## Важный статус

Это **фундамент автоматической P2P оплаты**.

Готово:

```text
карты в БД → выдача свободной карты → уникальная сумма → endpoint для входящих уведомлений → авто-матчинг → статус paid
```

Еще НЕ готово:

```text
реальный Telegram Business / банк-бот bridge, который будет пересылать сообщения банка в /api/payments/p2p/incoming
```

Следующий этап: подключить источник входящих банковских уведомлений.
