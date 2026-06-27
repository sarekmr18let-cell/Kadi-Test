from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


# ============= Auth =============
class TelegramAuthRequest(BaseModel):
    init_data: str = Field(..., description="Telegram WebApp InitData string")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ============= User =============
class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    language_code: Optional[str] = None
    id: int
    language_code: str = "ru"
    is_admin: bool
    is_blocked: bool
    balance: float
    referral_code: Optional[str] = None
    referral_bonus_earned: float
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    orders_count: int
    total_spent: float


class UserLanguageUpdate(BaseModel):
    language_code: str

    @field_validator("language_code")
    @classmethod
    def validate_language_code(cls, value: str) -> str:
        normalized = (value or "").lower()
        if normalized not in {"ru", "uz", "en"}:
            raise ValueError("language_code must be one of: ru, uz, en")
        return normalized


# ============= Category =============
class CategoryBase(BaseModel):
    name: str
    slug: str
    icon: Optional[str] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    moogold_id: Optional[int] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    moogold_id: Optional[int] = None


class CategoryResponse(CategoryBase):
    id: int
    moogold_id: Optional[int] = None
    is_active: bool
    
    class Config:
        from_attributes = True


# ============= Product Variation =============
class ProductImageResponse(BaseModel):
    id: int
    name: str
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class ProductVariationBase(BaseModel):
    name: str
    price: float
    cost_price: Optional[float] = None
    cost_currency: str = "UZS"
    stock_status: str = "instock"
    image_url: Optional[str] = None
    sort_order: int = 0


class ProductVariationCreate(ProductVariationBase):
    moogold_variation_id: Optional[int] = None
    provider: Optional[str] = "manual"
    provider_variation_id: Optional[str] = None
    provider_price: Optional[float] = None
    provider_currency: Optional[str] = None
    provider_meta: Optional[Dict[str, Any]] = None
    region: Optional[str] = None


class ProductVariationUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    cost_price: Optional[float] = None
    cost_currency: Optional[str] = None
    stock_status: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: Optional[int] = None
    moogold_variation_id: Optional[int] = None
    provider: Optional[str] = None
    provider_variation_id: Optional[str] = None
    provider_price: Optional[float] = None
    provider_currency: Optional[str] = None
    provider_meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    region: Optional[str] = None


class ProductVariationResponse(ProductVariationBase):
    id: int
    moogold_variation_id: Optional[int] = None
    product: Optional[ProductImageResponse] = None
    provider: Optional[str] = None
    provider_variation_id: Optional[str] = None
    provider_price: Optional[float] = None
    provider_currency: Optional[str] = None
    provider_meta: Optional[Dict[str, Any]] = None
    is_active: bool
    
    class Config:
        from_attributes = True


class ProductRegionOption(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=100)


# ============= Product =============
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int = 0
    availability_status: str = "available"

    # Dynamic account/region form requirements.
    target_type: str = Field(default="game_id", description="game_id, telegram_username, none")
    requires_target_id: bool = True
    requires_server_id: bool = False
    requires_region: bool = False
    target_id_label: str = "User ID / Game ID"
    target_server_label: str = "Server ID"
    target_region_label: str = "Region"
    region_options: List[ProductRegionOption] = Field(default_factory=list)
    input_help_text: Optional[str] = None

    @field_validator("availability_status", mode="before")
    @classmethod
    def validate_availability_status(cls, value) -> str:
        value = value or "available"
        allowed = {"available", "coming_soon", "maintenance", "hidden"}
        if value not in allowed:
            raise ValueError(f"availability_status must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        allowed = {"game_id", "telegram_username", "none"}
        if value not in allowed:
            raise ValueError(f"target_type must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("region_options", mode="before")
    @classmethod
    def parse_region_options(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception as exc:
                raise ValueError(f"region_options must be valid JSON: {exc}")
        return value


class ProductCreate(ProductBase):
    category_id: int
    moogold_id: Optional[int] = None


class ProductResponse(ProductBase):
    id: int
    category_id: int
    moogold_id: Optional[int] = None
    provider: Optional[str] = None
    provider_product_id: Optional[str] = None
    provider_meta: Optional[Dict[str, Any]] = None
    is_active: bool
    category: Optional[CategoryResponse] = None
    variations: List[ProductVariationResponse] = []
    
    class Config:
        from_attributes = True


class ProductListItem(BaseModel):
    id: int
    name: str
    image_url: Optional[str] = None
    min_price: float
    category_id: int
    category_slug: str
    target_type: str = "game_id"
    requires_target_id: bool = True
    requires_server_id: bool = False
    requires_region: bool = False
    availability_status: str = "available"


# ============= Order Item =============
class OrderItemCreate(BaseModel):
    variation_id: int
    quantity: int = Field(..., ge=1, le=10)


class OrderItemResponse(BaseModel):
    id: int
    variation: ProductVariationResponse
    quantity: int
    unit_price: float
    total_price: float
    
    class Config:
        from_attributes = True


# ============= Order =============
class OrderCreateRequest(BaseModel):
    items: List[OrderItemCreate]
    target_id: Optional[str] = Field(default=None, description="User ID / Game ID / Telegram username")
    target_server: Optional[str] = None
    target_region: Optional[str] = None
    promo_code: Optional[str] = None
    verified_target_name: Optional[str] = None
    verified_target_payload: Optional[Dict[str, Any]] = None

class OrderResponse(BaseModel):
    id: int
    user_id: int
    order_number: str
    status: str
    total_amount: float
    currency: str = "USD"
    target_id: Optional[str] = None
    target_server: Optional[str] = None
    target_region: Optional[str] = None
    target_region_label: Optional[str] = None
    verified_target_name: Optional[str] = None
    verified_target_payload: Optional[Dict[str, Any]] = None
    moogold_order_id: Optional[str] = None
    promo_code: Optional[str] = None
    discount_amount: float
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]
    
    class Config:
        from_attributes = True


class OrderPaymentRequest(BaseModel):
    payment_method: str
    payment_amount: float
    payment_receipt: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    status: str  # awaiting_payment, payment_submitted, paid, processing, completed, cancelled, refunded


# ============= Promo =============
class PromoApplyRequest(BaseModel):
    code: str
    order_amount: float


class PromoResponse(BaseModel):
    code: str
    type: str
    value: float
    discount_amount: float
    is_valid: bool
    message: Optional[str] = None


# ============= Payment =============
class PaymentMethodResponse(BaseModel):
    id: int
    name: str
    details: str
    instructions: Optional[str] = None


class PaymentCreateRequest(BaseModel):
    order_id: int
    method_id: int
    amount: float
    receipt: Optional[str] = None


# ============= Balance / Transaction =============
class BalanceResponse(BaseModel):
    currency: str = "UZS"
    balance: float


class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: float
    currency: str
    status: str
    description: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============= Admin =============
class DashboardStats(BaseModel):
    total_users: int
    total_orders: int
    total_revenue: float
    today_orders: int
    today_revenue: float
    pending_orders: int


class AdminOrderFilter(BaseModel):
    status: Optional[str] = None
    page: int = 1
    limit: int = 20


# ============= MooGold API Proxy =============
class MooGoldCreateOrderRequest(BaseModel):
    category: int = Field(..., gt=0, description="1=Direct Top Up, 2=eVouchers")
    product_id: int = Field(..., gt=0, alias="product-id")
    quantity: int = Field(..., ge=1, le=10)
    user_id: str = Field(..., min_length=1, alias="User ID")
    server: Optional[str] = Field(None, alias="Server")
    partner_order_id: Optional[str] = None


class MooGoldOrderResponse(BaseModel):
    status: bool
    message: str
    order_id: Optional[str] = None
    account_details: Optional[dict] = None


class MooGoldProductDetailResponse(BaseModel):
    product_name: str
    image_url: str
    variations: List[dict]


# ============= P2P Card Pool / Auto Parser =============
class P2PCardBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    bank_name: Optional[str] = None
    payment_system: str = Field(default="uzcard", description="uzcard, humo, visa, other")
    card_number: str = Field(..., min_length=12, max_length=32)
    card_holder: Optional[str] = None
    phone_number: Optional[str] = None
    min_amount: float = Field(default=0.0, ge=0)
    max_amount: Optional[float] = Field(default=None, ge=0)
    daily_limit: Optional[float] = Field(default=None, ge=0)
    is_active: bool = True
    sort_order: int = 0

    @field_validator("card_number")
    @classmethod
    def clean_card_number(cls, value: str) -> str:
        cleaned = "".join(ch for ch in value if ch.isdigit())
        if len(cleaned) < 12 or len(cleaned) > 32:
            raise ValueError("card_number must contain 12-32 digits")
        return cleaned


class P2PCardCreate(P2PCardBase):
    pass


class P2PCardUpdate(P2PCardBase):
    pass


class P2PCardResponse(P2PCardBase):
    id: int
    last4: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class P2PCardPublic(BaseModel):
    id: int
    name: str
    bank_name: Optional[str] = None
    payment_system: str
    card_number: str
    card_holder: Optional[str] = None
    phone_number: Optional[str] = None
    last4: str

    class Config:
        from_attributes = True


class P2PPaymentSessionResponse(BaseModel):
    id: int
    order_id: int
    status: str
    base_amount: float
    unique_amount: float
    assigned_amount: float
    expires_at: datetime
    created_at: datetime
    paid_at: Optional[datetime] = None
    card: P2PCardPublic

    class Config:
        from_attributes = True




class BalanceTopUpCreate(BaseModel):
    amount: float = Field(..., gt=0, description="UZS amount the user wants to add to balance")


class BalanceTopUpResponse(BaseModel):
    id: int
    user_id: int
    amount: float
    currency: str
    status: str
    expires_at: datetime
    created_at: datetime
    paid_at: Optional[datetime] = None
    note: Optional[str] = None
    card: P2PCardPublic

    class Config:
        from_attributes = True


class BalanceTopUpAdminUpdate(BaseModel):
    action: str = Field(..., description="approve, reject, cancel")
    note: Optional[str] = None


class P2PIncomingPaymentCreate(BaseModel):
    source: str = "telegram_bank_bot"
    raw_text: str = Field(..., min_length=5)
    amount: Optional[float] = Field(default=None, ge=0)
    card_last4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    external_id: Optional[str] = None


class P2PIncomingPaymentResponse(BaseModel):
    id: int
    source: str
    amount: Optional[float] = None
    currency: str
    card_last4: Optional[str] = None
    matched_order_id: Optional[int] = None
    matched_session_id: Optional[int] = None
    matched_topup_id: Optional[int] = None
    matched_user_id: Optional[int] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# ============= MooGold Fulfillment =============
class MooGoldFulfillmentResponse(BaseModel):
    id: int
    order_id: int
    order_item_id: int
    moogold_order_id: Optional[str] = None
    partner_order_id: str
    status: str
    error_message: Optional[str] = None
    attempts: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

