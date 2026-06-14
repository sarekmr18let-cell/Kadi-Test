# TG Shop — Architecture Documentation

> Generated from GitNexus Knowledge Graph
> Index: 1,035 nodes | 1,834 edges | 77 execution flows | 18 functional clusters

## Overview

TG Shop is a Telegram Mini App shop for virtual goods (game top-ups, gift cards, Telegram Stars/Premium). It integrates with the **MooGold API** for order fulfillment.

The architecture follows a classic three-tier pattern with async processing:
- **Frontend**: Vanilla JS Telegram Mini App (SPA)
- **Backend**: FastAPI with SQLAlchemy async ORM
- **Bot**: Aiogram for Telegram interactions
- **External**: MooGold API for product fulfillment

## Functional Areas

| Area | Symbols | Cohesion | Files | Purpose |
|------|---------|----------|-------|---------|
| **Services** | 18 | 1.0 | `moogold.py`, `notifications.py` | External API client + Celery tasks |
| **Models** | 11 | 1.0 | `models.py`, `base.py` | SQLAlchemy ORM entities |
| **Bot** | 11 | 1.0 | `bot/main.py`, `backend_client.py` | Telegram bot handlers |
| **API** | 11 | 1.0 | `auth.py`, `orders.py`, `admin.py`, etc. | FastAPI route handlers |
| **Schemas** | 9 | 1.0 | `schemas.py` | Pydantic request/response models |
| **Mini App JS** | 45 | 0.47–0.72 | `app.js`, `index.html`, `style.css` | Frontend SPA logic |
| **Alembic** | 4 | 1.0 | `alembic/` | Database migrations |
| **Core** | 5 | 1.0 | `config.py`, `security.py`, `database.py`, `limiter.py` | Shared infrastructure |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | FastAPI 0.111.0 |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 15 |
| Cache/Queue | Redis 7 |
| Task Queue | Celery 5.4 |
| Bot Framework | Aiogram |
| HTTP Client | httpx |
| Auth | JWT + Telegram InitData HMAC |
| Rate Limiting | slowapi |
| Reverse Proxy | Nginx |
| Frontend | Vanilla JS (SPA) |
| CSS | Custom glassmorphism theme |

## System Architecture

```mermaid
graph TB
    subgraph External["External Systems"]
        TG["Telegram Servers"]
        MG["MooGold API"]
        USER["User Browser"]
    end

    subgraph Frontend["Frontend Layer"]
        MA["Telegram Mini App<br/>Vanilla JS SPA<br/>webapp/js/app.js"]
    end

    subgraph Infrastructure["Infrastructure Layer"]
        NGINX["Nginx Reverse Proxy<br/>Port 80/443"]
        REDIS["Redis<br/>Cache + Task Queue"]
        PG["PostgreSQL 15<br/>Asyncpg Driver"]
    end

    subgraph Backend["Backend Layer (FastAPI)"]
        API["FastAPI App<br/>app.main:app"]
        AUTH["Auth Module<br/>JWT + Telegram InitData"]
        ORDERS["Orders Module<br/>P2P Payment Flow"]
        PRODUCTS["Products Module<br/>Catalog + Search"]
        ADMIN["Admin Module<br/>Dashboard + Management"]
        WEBHOOK["Webhook Module<br/>MooGold Callbacks"]
        MOOGOLD["MooGold Proxy<br/>Admin-only API passthrough"]
        USERS["Users Module<br/>Profile + Balance"]
        PAYMENTS["Payments Module<br/>P2P Methods"]
    end

    subgraph Workers["Background Workers"]
        CELERY["Celery Workers<br/>Notifications + Expired Orders"]
        BEAT["Celery Beat<br/>Scheduled Tasks"]
    end

    subgraph BotLayer["Bot Layer"]
        BOT["Aiogram Bot<br/>Commands + WebApp Menu"]
    end

    USER -->|Open from Telegram| MA
    MA -->|API calls + Bearer JWT| NGINX
    NGINX -->|/api/* → backend:8000| API
    NGINX -->|Static files| MA

    TG -->|InitData + Callbacks| BOT
    BOT -->|Backend REST API| API

    API -->|SQLAlchemy Async| PG
    API -->|Redis Queue| REDIS
    REDIS -->|Consume Tasks| CELERY
    CELERY -->|Telegram Bot API| TG
    BEAT -->|Schedule| REDIS

    API -->|HMAC-SHA256 Auth| MG
    MG -->|Signed Webhooks| WEBHOOK
    WEBHOOK -->|Update Status| ORDERS
    ORDERS -->|Celery Task| REDIS

    AUTH -.->|Token Validation| API
    MOOGOLD -.->|Admin Check| AUTH
    ADMIN -.->|Admin Check| AUTH

    style External fill:#e1f5fe
    style Frontend fill:#fff3e0
    style Backend fill:#e8f5e9
    style Workers fill:#fce4ec
    style Infrastructure fill:#f3e5f5
    style BotLayer fill:#e0f2f1
```

## API Routes (31 Endpoints)

| Prefix | Routes | Module | Auth |
|--------|--------|--------|------|
| `/api/auth` | `/telegram`, `/refresh`, `/me` | Auth | Telegram InitData / JWT |
| `/api/products` | `/categories`, `/{id}`, `/category/{slug}` | Products | Public |
| `/api/orders` | `/`, `/my`, `/{id}`, `/{id}/pay`, `/apply-promo` | Orders | JWT |
| `/api/payments` | `/methods`, `/methods/{id}` | Payments | JWT |
| `/api/users` | `/profile`, `/balance`, `/transactions`, `/referral-link` | Users | JWT |
| `/api/admin` | `/dashboard`, `/orders`, `/products`, `/users`, etc. | Admin | Admin JWT |
| `/api/moogold` | `/order`, `/order-detail`, `/products`, `/balance` | MooGold Proxy | Admin JWT |
| `/api/webhook` | `/moogold` | Webhook | HMAC Signature |
| `/api/health` | `/` | Health | Public |

## Key Execution Flows

### 1. User Authentication Flow

```mermaid
sequenceDiagram
    participant U as User Browser
    participant TG as Telegram
    participant MA as Mini App
    participant API as FastAPI
    participant DB as PostgreSQL

    U->>TG: Open Mini App
    TG->>MA: Provide InitData (signed)
    MA->>API: POST /auth/telegram<br/>{init_data}
    API->>API: Verify HMAC signature<br/>against BOT_TOKEN
    API->>DB: SELECT/INSERT user
    API->>DB: Check is_blocked
    API->>API: Generate JWT + Refresh tokens
    API->>MA: Return {access_token, refresh_token}
    MA->>MA: Store in localStorage (safeSet)
    MA->>API: GET /auth/me<br/>Authorization: Bearer {token}
    API->>DB: Fetch user profile
    API->>MA: Return UserProfile
```

**Key Security:**
- Telegram InitData HMAC verification with 24h freshness check
- JWT tokens: 15min access, 7-day refresh
- Admin status re-checked from database on every admin request (stale token protection)
- Rate limiting: 5 requests/minute on `/auth/telegram`

### 2. Place Order + P2P Payment Flow

```mermaid
sequenceDiagram
    participant MA as Mini App
    participant API as FastAPI
    participant DB as PostgreSQL
    participant REDIS as Redis
    participant CELERY as Celery Worker
    participant ADMIN as Admin (Telegram)
    participant U as User

    MA->>API: POST /orders<br/>{items, target_id, target_server, promo_code}
    API->>DB: Validate variations + stock
    API->>DB: Check promo code validity
    API->>DB: INSERT order (status: awaiting_payment)
    API->>DB: INSERT order_items
    API->>REDIS: Task: send_order_notification
    API->>MA: Return OrderResponse

    CELERY->>DB: Fetch order details
    CELERY->>U: Telegram: "Awaiting Payment"

    U->>MA: Transfer money, click "I Have Paid"
    MA->>API: POST /orders/{id}/pay<br/>{payment_method, amount, receipt}
    API->>DB: UPDATE order status → paid
    API->>REDIS: Task: notify admin
    API->>MA: Return updated order

    CELERY->>ADMIN: Telegram: "New paid order"

    ADMIN->>API: POST /admin/orders/{id}/status<br/>{status: completed}
    API->>DB: UPDATE order → completed
    API->>DB: INSERT transaction record
    API->>REDIS: Task: notify user
    API->>ADMIN: Success

    CELERY->>U: Telegram: "Order Completed!"
```

**Key Logic:**
- Quantity validation: 1–10 per item
- Payment amount must match order total (±0.01)
- Order can only be paid once (status == awaiting_payment)
- Only admin can move from paid → completed

### 3. MooGold Webhook Flow

```mermaid
sequenceDiagram
    participant MG as MooGold API
    participant NGINX as Nginx
    participant API as FastAPI Webhook
    participant DB as PostgreSQL
    participant REDIS as Redis
    participant CELERY as Celery Worker
    participant U as User

    MG->>NGINX: POST /api/webhook/moogold<br/>X-Signature: HMAC
    NGINX->>API: Forward request
    API->>API: Verify HMAC-SHA256<br/>against MOOGOLD_SECRET_KEY
    API->>API: Parse MooGoldWebhookPayload
    API->>DB: SELECT order by moogold_order_id
    alt Order not found
        API->>DB: SELECT by partner_order_id
    end
    API->>API: Validate status ∈ {completed, refunded, cancelled, processing}
    API->>DB: UPDATE order.status
    API->>DB: Store account_details (≤1000 chars)
    API->>REDIS: Task: send_order_notification
    API->>MG: {status: success}

    CELERY->>U: Telegram: Status update message
```

**Key Security:**
- HMAC-SHA256 signature verification on every webhook
- Status whitelist: only 4 valid statuses accepted
- Payload size limits on account_details

### 4. Admin Dashboard Flow

```mermaid
sequenceDiagram
    participant MA as Mini App (Admin)
    participant API as FastAPI Admin
    participant AUTH as Security Layer
    participant DB as PostgreSQL

    MA->>API: GET /admin/dashboard<br/>Authorization: Bearer {token}
    API->>AUTH: get_current_admin
    AUTH->>AUTH: decode JWT
    AUTH->>DB: SELECT user WHERE is_admin = true
    AUTH->>API: Return user dict
    API->>DB: COUNT users, orders
    API->>DB: SUM revenue (completed)
    API->>DB: COUNT today orders
    API->>DB: COUNT pending (paid status)
    API->>MA: DashboardStats
```

**Key Security:**
- Admin token validated + database re-check on every request
- No hardcoded admin logic — all admin checks query DB

### 5. Celery Notification Flow

```mermaid
sequenceDiagram
    participant BEAT as Celery Beat
    participant REDIS as Redis Queue
    participant CELERY as Celery Worker
    participant DB as PostgreSQL (sync)
    participant TG as Telegram API

    alt Scheduled Task
        BEAT->>REDIS: Enqueue cancel_expired_orders
    end
    alt Order Status Change
        API->>REDIS: Enqueue send_order_notification
    end

    REDIS->>CELERY: Deliver task
    CELERY->>DB: Sync session: fetch order + user
    CELERY->>CELERY: escape_html() on user data
    CELERY->>CELERY: Format HTML message
    CELERY->>TG: POST /bot{token}/sendMessage<br/>(sync httpx)
    CELERY->>TG: Send to admin if ADMIN_TG_ID valid
```

**Key Points:**
- Celery uses sync SQLAlchemy engine (psycopg2) because Celery tasks run in sync context
- HTML escaping before Telegram sendMessage (prevents XSS via Telegram HTML parse_mode)
- Graceful handling of missing/invalid ADMIN_TG_ID

## Data Model

### Core Entities

| Entity | Key Fields | Relationships |
|--------|-----------|--------------|
| **User** | telegram_id, username, balance, is_admin, is_blocked, referral_code | → orders, transactions |
| **Category** | moogold_id, name, slug, icon, sort_order | → products |
| **Product** | moogold_id, category_id, name, description, image_url | → category, variations |
| **ProductVariation** | product_id, name, price, stock_status | → product, order_items |
| **Order** | order_number, user_id, status, total_amount, discount_amount, target_id, target_server, moogold_order_id, partner_order_id | → user, items, transactions |
| **OrderItem** | order_id, variation_id, quantity, unit_price, total_price | → order, variation |
| **Transaction** | user_id, order_id, type, amount, status, description | → user, order |
| **PromoCode** | code, type, value, min_order_amount, max_discount, usage_limit, usage_count, valid_from, valid_until | — |
| **PaymentMethod** | name, details, instructions, sort_order | — |

### Database Constraints

Added `CheckConstraint` on key numeric fields:
- `ProductVariation.price >= 0`
- `Order.total_amount >= 0`, `payment_amount >= 0`, `discount_amount >= 0`
- `OrderItem.quantity > 0`, `unit_price >= 0`, `total_price >= 0`
- `Transaction.amount >= 0`
- `PromoCode.value >= 0`, `min_order_amount >= 0`, `max_discount >= 0`, `usage_limit >= 0`

## Deployment

```mermaid
graph LR
    subgraph "Docker Compose"
        direction TB
        nginx[Nginx<br/>Port 80/443]
        backend[Backend<br/>Uvicorn 8000]
        bot[Telegram Bot]
        celery[Celery Worker]
        beat[Celery Beat]
        postgres[PostgreSQL 15]
        redis[Redis 7]
    end

    internet[Internet] --> nginx
    nginx --> backend
    nginx -->|Static files| webapp[webapp/]
    backend --> postgres
    backend --> redis
    celery --> redis
    celery --> postgres
    beat --> redis
    bot --> backend

    backend -.->|Volume| uploads[uploads/]
    nginx -.->|Volume| uploads
```

## Security Architecture

| Layer | Measures |
|-------|----------|
| **Auth** | Telegram InitData HMAC + JWT (HS256, 32+ char secret) |
| **Admin** | DB re-check on every request (no stale tokens) |
| **Rate Limiting** | 5/min on auth endpoints via slowapi |
| **CORS** | Restricted to FRONTEND_URL + *.telegram.org |
| **Webhooks** | HMAC-SHA256 signature verification |
| **XSS** | `escapeHtml()` helper on all Mini App innerHTML |
| **Input Validation** | Pydantic schemas + manual validation on all endpoints |
| **Database** | SQLAlchemy ORM (no raw SQL), CheckConstraints on numeric fields |
| **Notifications** | HTML escaping before Telegram sendMessage |

## Configuration

Critical env vars (validated at startup):
- `JWT_SECRET` — must be ≥32 characters
- `BOT_TOKEN` — validated format (Telegram bot tokens start with `7`)
- `MOOGOLD_PARTNER_ID` + `MOOGOLD_SECRET_KEY` — for API auth
- `ADMIN_TG_ID` — numeric Telegram ID for first admin

---

*Generated: 2026-06-10 via GitNexus Knowledge Graph*
*Index: 1,035 nodes | 1,834 edges | 77 flows | 18 clusters*