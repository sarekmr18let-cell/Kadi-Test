# 🎮 TG Shop — Telegram Mini App Store

Telegram Mini App магазин виртуальных товаров (игровые топ-апы, подарочные карты, Telegram Stars/Premium). Интеграция с **MooGold API** для выполнения заказов.

---

## 📋 Содержание

- [Требования](#требования)
- [Быстрый старт (Docker)](#быстрый-старт-docker)
- [Настройка Telegram Bot](#настройка-telegram-bot)
- [Настройка MooGold](#настройка-moogold)
- [Локальный запуск (без Docker)](#локальный-запуск-без-docker)
- [Продакшен деплой](#продакшен-деплой)
- [Архитектура](#архитектура)
- [API Endpoints](#api-endpoints)
- [Устранение неполадок](#устранение-неполадок)
- [Разработка](#разработка)

---

## 📌 Требования

| Компонент | Версия |
|-----------|--------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Git | 2.30+ |
| Python | 3.12+ (только для локальной разработки) |
| Telegram аккаунт | Для настройки бота |

---

## 🚀 Быстрый старт (Docker)

### Шаг 1: Клонирование

```bash
git clone <repo-url>
cd tgbot
```

### Шаг 2: Настройка окружения

```bash
# Скопируйте шаблон
cp .env.example .env

# Отредактируйте .env (см. ниже обязательные переменные)
nano .env
```

### Шаг 3: Обязательные переменные .env

```bash
# === ОБЯЗАТЕЛЬНО ===

# Telegram Bot (получить у @BotFather)
BOT_TOKEN=710123456:ABCdefGHIjklMNOpqrsTUVwxyz123456789
ADMIN_TG_ID=123456789              # Ваш numeric Telegram ID
BOT_USERNAME=myshopbot             # Без @

# База данных
POSTGRES_USER=tgbot
POSTGRES_PASSWORD=super_strong_password_123
POSTGRES_DB=tgbot

# JWT (минимум 32 символа!)
JWT_SECRET=your-super-secret-key-min-32-chars-long

# MooGold API (получить у менеджера MooGold)
MOOGOLD_PARTNER_ID=your_partner_id
MOOGOLD_SECRET_KEY=your_secret_key

# URL-ы
WEBAPP_URL=https://tgbot.example.com
CALLBACK_BASE_URL=https://tgbot.example.com
```

**Как получить ADMIN_TG_ID:**
```
1. Напишите @userinfobot в Telegram
2. Он отправит ваш numeric ID
3. Скопируйте это число в ADMIN_TG_ID
```

**Как получить BOT_TOKEN:**
```
1. Напишите @BotFather в Telegram
2. /newbot → введите имя бота
3. Скопируйте токен в BOT_TOKEN
4. /setmenubutton → выберите Mini App URL
```

### Шаг 4: Запуск

```bash
# Собрать и запустить ВСЕ сервисы
docker compose up --build -d

# Проверить статус
docker compose ps

# Проверить логи
docker compose logs -f backend
```

### Шаг 5: Проверка работы

| Сервис | URL | Статус |
|--------|-----|--------|
| Mini App | `http://localhost` | Должен открываться |
| API Health | `http://localhost/api/health` | `{"status":"ok"}` |
| API Docs | `http://localhost/api/docs` | Swagger UI |
| Backend | `http://localhost:8000` | FastAPI |

### Шаг 6: Миграции базы данных

```bash
# При первом запуске или после обновления
docker compose exec backend alembic upgrade head
```

### Шаг 7: Остановка

```bash
# Остановить все сервисы
docker compose down

# Остановить и удалить данные (⚠️ удалит БД!)
docker compose down -v
```

---

## 🤖 Настройка Telegram Bot

### 1. Создание бота

```
@BotFather → /newbot
- Имя бота: My Shop
- Username: myshopbot (должен оканчиваться на bot)
- Получите BOT_TOKEN
```

### 2. Настройка Mini App кнопки

```
@BotFather → /mybots → myshopbot → Bot Settings → Menu Button
- Configure menu button
- Выберите "Open Web App"
- URL: https://your-domain.com (или http://localhost для теста)
```

### 3. Настройка домена (для продакшена)

```
@BotFather → /mybots → myshopbot → Bot Settings → Mini App
- Configure Mini App
- Добавьте ваш домен
- Подтвердите через DNS или файл
```

---

## 🏪 Настройка MooGold

### 1. Регистрация

- Зарегистрируйтесь на [moogold.com](https://moogold.com)
- Получите PARTNER_ID и SECRET_KEY у менеджера

### 2. Настройка webhook

В дашборде MooGold:
```
Webhook URL: https://your-domain.com/api/webhook/moogold
Callback URL: https://your-domain.com/api/webhook/moogold
```

### 3. Баланс

- Пополните баланс в MooGold для автоматического выполнения заказов
- Или используйте ручной режим через админ-панель

---

## 💻 Локальный запуск (без Docker)

### Требования

```bash
# macOS
brew install postgresql@15 redis python@3.12

# Ubuntu/Debian
sudo apt update
sudo apt install postgresql-15 redis-server python3.12 python3.12-venv

# Запустите PostgreSQL и Redis
brew services start postgresql@15  # macOS
brew services start redis           # macOS

sudo systemctl start postgresql     # Linux
sudo systemctl start redis-server    # Linux
```

### Backend

```bash
cd backend

# Виртуальное окружение
python3.12 -m venv venv
source venv/bin/activate  # Linux/macOS
# или: venv\Scripts\activate  # Windows

# Зависимости
pip install -r requirements.txt

# База данных
createdb tgbot
alembic upgrade head

# Запуск
export $(cat ../.env | xargs)  # Загрузить переменные окружения
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Mini App)

```bash
# Mini App статические файлы уже в backend/app/webapp_static/
# Nginx или просто откройте webapp/index.html

# Для теста без Telegram:
cd webapp
python3 -m http.server 8080
# Откройте http://localhost:8080
# ⚠️ Авторизация не будет работать без Telegram InitData
```

### Bot

```bash
cd bot

# Виртуальное окружение
python3.12 -m venv venv
source venv/bin/activate

# Зависимости
pip install aiogram httpx

# Запуск
export $(cat ../.env | xargs)
python main.py
```

### Celery (Background Tasks)

```bash
cd backend
source venv/bin/activate
export $(cat ../.env | xargs)

# Worker
celery -A app.celery_app worker --loglevel=info

# Scheduler (в другом терминале)
celery -A app.celery_app beat --loglevel=info
```

---

## 🌐 Продакшен деплой

### Серверные требования

| Спецификация | Минимум | Рекомендуется |
|-------------|---------|---------------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Disk | 10 GB SSD | 20 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Деплой на VPS

```bash
# 1. Клонирование
git clone <repo-url>
cd tgbot

# 2. Настройка .env (см. выше)
cp .env.example .env
nano .env

# 3. SSL сертификаты (Let's Encrypt)
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# 4. Docker Compose
docker compose up --build -d

# 5. Миграции
docker compose exec backend alembic upgrade head

# 6. Проверка
curl https://your-domain.com/api/health
```

### Nginx SSL конфигурация

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # API proxy
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Static files
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

### Обновление (Zero-downtime)

```bash
# 1. Получить обновления
git pull origin main

# 2. Пересобрать
docker compose up --build -d

# 3. Миграции
docker compose exec backend alembic upgrade head

# 4. Проверка
docker compose ps
docker compose logs -f backend
```

---

## 🏗 Архитектура

```
tgbot/
├── docker-compose.yml          # Инфраструктура: postgres, redis, backend, bot, nginx
├── .env.example                # Шаблон конфигурации
├── .env                        # Ваши секреты (не коммитить!)
│
├── backend/                    # FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint + CORS + lifespan
│   │   ├── celery_app.py       # Celery конфигурация
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic Settings + валидация
│   │   │   ├── security.py     # JWT + Telegram InitData HMAC + admin check
│   │   │   ├── database.py     # Async SQLAlchemy engine + session
│   │   │   └── limiter.py      # Rate limiting (slowapi)
│   │   ├── models/
│   │   │   ├── base.py         # SQLAlchemy Base
│   │   │   └── models.py       # Все ORM модели + CheckConstraints
│   │   ├── schemas/
│   │   │   └── schemas.py      # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── __init__.py     # Router imports
│   │   │   ├── auth.py         # Telegram auth + JWT tokens
│   │   │   ├── products.py     # Каталог товаров
│   │   │   ├── orders.py       # Создание/оплата заказов + промокоды
│   │   │   ├── payments.py     # P2P методы оплаты
│   │   │   ├── users.py        # Профиль + баланс + транзакции
│   │   │   ├── admin.py        # Админ панель + dashboard
│   │   │   ├── moogold_proxy.py # Прокси к MooGold API (admin only)
│   │   │   └── webhook.py      # Webhook от MooGold (HMAC verified)
│   │   ├── services/
│   │   │   ├── moogold.py      # MooGold API client (HMAC auth)
│   │   │   └── notifications.py # Celery tasks + Telegram notifications
│   │   └── webapp_static/      # Статика Mini App (копия webapp/)
│   ├── alembic/                # Миграции базы данных
│   ├── requirements.txt        # Python зависимости
│   └── Dockerfile              # Backend image
│
├── bot/                        # Aiogram 3 Telegram Bot
│   ├── main.py                 # Handlers + commands + WebApp menu
│   ├── services/
│   │   └── backend_client.py  # HTTP client для backend API
│   └── Dockerfile              # Bot image
│
├── webapp/                     # Mini App (исходники)
│   ├── index.html              # Главная страница
│   ├── css/
│   │   └── style.css           # Neon glassmorphism theme
│   └── js/
│       └── app.js              # SPA: routing, cart, auth, checkout
│
├── nginx/
│   └── nginx.conf              # Reverse proxy + security headers
│
└── ARCHITECTURE.md             # Подробная архитектурная документация
```

### Компоненты системы

| Компонент | Порт | Описание |
|-----------|------|----------|
| Nginx | 80/443 | Reverse proxy, static files |
| Backend | 8000 | FastAPI, REST API |
| PostgreSQL | 5432 | База данных |
| Redis | 6379 | Кэш, очередь задач |
| Bot | — | Telegram Bot ( polling ) |
| Celery Worker | — | Background tasks |
| Celery Beat | — | Scheduled tasks |

---

## 🔌 API Endpoints

### Auth
```
POST /api/auth/telegram       # Telegram InitData → JWT
POST /api/auth/refresh      # Refresh token → новый access token
GET  /api/auth/me           # Профиль текущего пользователя
```

### Products (Public)
```
GET /api/products/categories           # Список категорий
GET /api/products?search=&category_id=  # Список товаров
GET /api/products/{id}                  # Детали товара
GET /api/products/category/{slug}     # Товары по категории
```

### Orders (JWT Required)
```
POST /api/orders                        # Создать заказ
GET  /api/orders/my                     # Мои заказы
GET  /api/orders/{id}                   # Детали заказа
POST /api/orders/{id}/pay               # Отметить оплату (P2P)
POST /api/orders/apply-promo            # Применить промокод
```

### Payments (JWT Required)
```
GET /api/payments/methods               # P2P методы оплаты
GET /api/payments/methods/{id}          # Детали метода
```

### Users (JWT Required)
```
GET /api/users/profile                  # Профиль
GET /api/users/balance                  # Баланс
GET /api/users/transactions             # История транзакций
GET /api/users/referral-link            # Реферальная ссылка
```

### Admin (Admin JWT Required)
```
GET  /api/admin/dashboard               # Статистика
GET  /api/admin/orders                  # Все заказы
POST /api/admin/orders/{id}/status      # Обновить статус
GET  /api/admin/products                # Список товаров
POST /api/admin/products                # Создать товар
PUT  /api/admin/products/{id}          # Обновить товар
DELETE /api/admin/products/{id}         # Деактивировать товар
GET  /api/admin/categories             # Категории
POST /api/admin/categories             # Создать категорию
GET  /api/admin/users                  # Пользователи
POST /api/admin/users/{id}/block       # Заблокировать
POST /api/admin/users/{id}/unblock     # Разблокировать
POST /api/admin/promo-codes            # Создать промокод
GET  /api/admin/transactions           # Транзакции
```

### MooGold Proxy (Admin Only)
```
POST /api/moogold/order           # Создать заказ в MooGold
POST /api/moogold/order-detail    # Детали заказа MooGold
POST /api/moogold/products        # Список продуктов MooGold
POST /api/moogold/product-detail  # Детали продукта MooGold
POST /api/moogold/balance         # Баланс MooGold
```

### Webhook (MooGold → Backend)
```
POST /api/webhook/moogold    # MooGold callbacks (HMAC verified)
```

### Health
```
GET /api/health              # Проверка здоровья + статус БД
```

---

## 🛠 Устранение неполадок

### Проблема: `ModuleNotFoundError: No module named 'jose'`

**Решение:**
```bash
cd backend
pip install -r requirements.txt
```

### Проблема: `Cannot connect to database`

**Решение:**
```bash
# Проверить статус PostgreSQL
docker compose ps

# Перезапустить
docker compose restart postgres

# Проверить подключение
docker compose exec postgres psql -U tgbot -d tgbot -c "SELECT 1"
```

### Проблема: Бот не отвечает

**Решение:**
```bash
# Проверить логи бота
docker compose logs -f bot

# Проверить BOT_TOKEN
docker compose exec bot echo $BOT_TOKEN

# Перезапустить
docker compose restart bot
```

### Проблема: Mini App не открывается

**Решение:**
```bash
# Проверить nginx
docker compose logs -f nginx

# Проверить статику
curl http://localhost/index.html

# Проверить CORS
curl -H "Origin: https://web.telegram.org" http://localhost/api/health
```

### Проблема: `ImportError: cannot import name 'limiter'`

**Решение:**
```bash
# Circular import — пересобрать
docker compose down
docker compose up --build -d
```

### Проблема: Миграции не применяются

**Решение:**
```bash
# Вручную
docker compose exec backend alembic upgrade head

# Если ошибка — создать заново
docker compose exec backend alembic revision --autogenerate -m "init"
docker compose exec backend alembic upgrade head
```

### Проблема: Celery задачи не выполняются

**Решение:**
```bash
# Проверить Redis
docker compose exec redis redis-cli ping

# Перезапустить workers
docker compose restart celery_worker celery_beat

# Проверить логи
docker compose logs -f celery_worker
```

---

## 🧪 Разработка

### Добавление нового API endpoint

```python
# backend/app/api/my_module.py
from fastapi import APIRouter, Depends
from app.core.security import get_current_user

router = APIRouter()

@router.get("/my-endpoint")
async def my_endpoint(current_user: dict = Depends(get_current_user)):
    return {"message": "Hello!"}
```

```python
# backend/app/api/__init__.py
from .my_module import router as my_module
```

```python
# backend/app/main.py
app.include_router(my_module.router, prefix="/api/my-module", tags=["My Module"])
```

### Создание миграции

```bash
cd backend
alembic revision --autogenerate -m "add new table"
alembic upgrade head
```

### Тестирование без Telegram

```bash
# Временно отключить Telegram InitData проверку
# backend/app/api/auth.py — закомментируйте verify_telegram_init_data
# Создайте mock JWT для теста
```

### Hot reload (только для разработки)

```bash
# backend/app/main.py — uvicorn с --reload уже настроен в docker-compose.yml
# Изменения в backend/app/ применяются автоматически
```

---

## 🔐 Безопасность

- **JWT_SECRET** — минимум 32 символа, храните в `.env`
- **MOOGOLD_SECRET_KEY** — никому не показывайте
- **ADMIN_TG_ID** — первый зарегистрированный пользователь с этим ID получает `is_admin=true`
- **Webhook** — MooGold webhook подписан HMAC-SHA256, подделать невозможно
- **Rate Limiting** — 5 запросов/мин на `/auth/telegram`
- **CORS** — ограничен доменом Mini App и *.telegram.org

---

## 📞 Поддержка

Если что-то не работает:

1. Проверьте `docker compose logs`
2. Проверьте `.env` (все переменные заполнены?)
3. Проверьте `docker compose ps` (все контейнеры Running?)
4. Проверьте `/api/health` (база данных подключена?)
5. Загляните в `ARCHITECTURE.md` для подробной архитектуры

---

**Удачного запуска! 🚀**