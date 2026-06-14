# GPT Fixes v1

Первый безопасный пакет правок для TG Shop.

## Что исправлено

1. **Bot ↔ Backend endpoints**
   - Добавлен новый защищённый роутер `backend/app/api/bot_internal.py`.
   - Бот больше не ходит в несуществующие `/api/users/profile/{telegram_id}`.
   - Теперь бот использует:
     - `/api/bot/profile/{telegram_id}`
     - `/api/bot/orders/{telegram_id}`
     - `/api/bot/balance/{telegram_id}`
     - `/api/bot/referral`
   - Эндпоинты защищены заголовком `X-Bot-Secret`.

2. **INTERNAL_BOT_SECRET**
   - Добавлена переменная `INTERNAL_BOT_SECRET` в:
     - `backend/app/core/config.py`
     - `docker-compose.yml`
     - `.env.example`
   - Backend и bot должны иметь одинаковое значение.

3. **Callback bug в боте**
   - Исправлены inline-кнопки `My Orders` и `Balance`.
   - Раньше callback мог использовать ID бота вместо ID пользователя.

4. **Фильтр категорий во frontend**
   - `ProductListItem` теперь отдаёт `category_id`.
   - `webapp/js/app.js` фильтрует по `category_id` корректно.

5. **Порядок маршрутов products**
   - Исправлен риск, когда `/products/category/{slug}` мог конфликтовать с `/products/{product_id}`.

6. **Eager loading для Order/Product**
   - Добавлен `selectinload`, чтобы API не падал на async lazy-loading при сериализации заказов/товаров.

7. **Промокоды**
   - `usage_count` больше не увеличивается при создании неоплаченного заказа.
   - Теперь промокод считается использованным только после успешной оплаты.
   - Невалидный промокод теперь блокирует создание заказа, а не создаёт заказ с промокодом без скидки.

8. **Безопасность пользователя**
   - `get_current_user` теперь проверяет пользователя в БД на каждом защищённом запросе.
   - Заблокированный пользователь теряет доступ сразу, а не после окончания JWT.
   - Refresh token тоже проверяет активность пользователя.

9. **Админ API для вариаций товара**
   - Добавлены endpoints:
     - `POST /api/admin/products/{product_id}/variations`
     - `PUT /api/admin/variations/{variation_id}`
     - `DELETE /api/admin/variations/{variation_id}`
   - Это нужно для товаров типа `86 diamonds`, `172 diamonds`, `257 diamonds`.

10. **Docker JWT default**
    - Исправлен дефолт `JWT_SECRET`; старый `supersecret` был короче 32 символов и мог ломать запуск.

## Что важно сделать после установки

В `.env` добавь:

```env
INTERNAL_BOT_SECRET=любая_случайная_строка_минимум_32_символа
```

Пример:

```env
INTERNAL_BOT_SECRET=change_this_internal_bot_secret_123456
```

Потом пересобери контейнеры:

```bash
docker compose up -d --build
```

## Что не трогалось в этом пакете

- Автоматическая отправка заказа в MooGold после оплаты.
- Полноценный UI для добавления товаров в Mini App.
- Автоматическое подтверждение P2P оплат через банковского бота.
- Перевод денег с `Float` на `Numeric`.

Это лучше делать отдельными этапами, чтобы не сломать проект одним большим изменением.
