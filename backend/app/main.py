from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import os

from app.core.database import engine, AsyncSessionLocal
from app.core.config import settings
from app.core.limiter import limiter
from app.api import auth, products, orders, admin, users, payments, moogold_proxy, webhook, bot_internal

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    os.makedirs("uploads", exist_ok=True)
    
    # Test database connection
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
    except Exception as e:
        import logging
        logging.error(f"Database connection failed: {e}")
        raise RuntimeError(f"Cannot connect to database: {e}")
    
    yield
    
    # Shutdown
    await engine.dispose()


# CORS: restrict to frontend URL only
FRONTEND_ORIGINS = [
    settings.FRONTEND_URL,
    "https://web.telegram.org",  # Telegram WebApp
    "https://*.telegram.org",     # Telegram domains
]

app = FastAPI(
    title="TG Shop API",
    description="Telegram Mini App Shop API with MooGold integration",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Bot-Secret", "X-P2P-Secret"],
    expose_headers=["X-Total-Count"],
    max_age=600,
)

# API Routes
app.include_router(auth, prefix="/api/auth", tags=["Auth"])
app.include_router(products, prefix="/api/products", tags=["Products"])
app.include_router(orders, prefix="/api/orders", tags=["Orders"])
app.include_router(payments, prefix="/api/payments", tags=["Payments"])
app.include_router(users, prefix="/api/users", tags=["Users"])
app.include_router(bot_internal, prefix="/api/bot", tags=["Bot Internal"])
app.include_router(admin, prefix="/api/admin", tags=["Admin"])
app.include_router(moogold_proxy, prefix="/api/moogold", tags=["MooGold Proxy"])
app.include_router(webhook, prefix="/api/webhook", tags=["Webhooks"])

# Static files (Mini App)
app.mount("/", StaticFiles(directory="app/webapp_static", html=True), name="static")


@app.get("/api/health")
async def health_check():
    """Health check endpoint with database connectivity test."""
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": "1.0.0",
    }
