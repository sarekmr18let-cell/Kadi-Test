from pydantic_settings import BaseSettings
from functools import lru_cache
from pydantic import field_validator


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://tgbot:tgbot_secret@postgres:5432/tgbot"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Telegram
    BOT_TOKEN: str = ""
    BOT_USERNAME: str = ""
    ADMIN_TG_ID: str = ""
    INTERNAL_BOT_SECRET: str = ""
    P2P_WEBHOOK_SECRET: str = ""
    
    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    
    # MooGold API
    MOOGOLD_PARTNER_ID: str = ""
    MOOGOLD_SECRET_KEY: str = ""
    MOOGOLD_BASE_URL: str = "https://moogold.com/wp-json/v1/api"
    MOOGOLD_AUTO_FULFILL_ENABLED: bool = True
    MOOGOLD_DEFAULT_ORDER_CATEGORY: int = 1  # 1=Direct Top Up, 2=eVouchers
    MOOGOLD_TEST_MODE: bool = False  # True = no real MooGold purchases; returns fake order IDs

    # GameDrops API
    GAMEDROPS_API_TOKEN: str = ""
    GAMEDROPS_BASE_URL: str = "https://partner.gamesdrop.io"
    GAMEDROPS_CIRCUIT_BREAKER_ENABLED: bool = True
    GAMEDROPS_CIRCUIT_BREAKER_TTL_SECONDS: int = 1800
    GAMEDROPS_BALANCE_GUARD_ENABLED: bool = True
    GAMEDROPS_BALANCE_GUARD_INTERVAL_SECONDS: int = 300
    GAMEDROPS_BALANCE_WARNING_DEDUPE_TTL_SECONDS: int = 3600
    GAMEDROPS_MIN_BALANCE_USD: float = 5.0
    PROVIDER_BALANCE_USD_RATE: float = 12400.0

    # PayStars API
    PAYSTARS_API_KEY: str = ""
    PAYSTARS_BASE_URL: str = "https://paystars.uz/api/v1"

    # Provider safety
    PROVIDER_AUTO_FULFILL_ENABLED: bool = False
    FULFILLMENT_RESCUE_DELAY_SECONDS: int = 90
    FULFILLMENT_RESCUE_MAX_AGE_SECONDS: int = 1800
    FULFILLMENT_RESCUE_DEDUPE_TTL_SECONDS: int = 300

    # P2P / wallet safety
    P2P_TEST_MODE: bool = False  # True = admin can run safe parser/process tests
    P2P_PAYMENT_TTL_MINUTES: int = 5
    WALLET_TOPUP_MIN_AMOUNT: float = 1000.0
    WALLET_TOPUP_MAX_AMOUNT: float = 5000000.0
    
    # App URLs
    CALLBACK_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "https://www.kadi-store.uz"
    WEBAPP_URL: str = "https://www.kadi-store.uz"
    
    @field_validator('JWT_SECRET')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return v
    
    @field_validator('BOT_TOKEN')
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        # Telegram bot tokens normally look like: 123456789:AA...
        # Do not check the first digit because new bot IDs are not guaranteed to start with 7.
        if v and (':' not in v or len(v) < 30):
            raise ValueError("BOT_TOKEN appears invalid")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
