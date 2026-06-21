from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, BigInteger, CheckConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone

from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    
    # Referral
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    referral_code = Column(String(50), unique=True, nullable=True)
    referral_bonus_earned = Column(Float, default=0.0)
    
    orders = relationship("Order", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    balance_topups = relationship("BalanceTopUp", back_populates="user")


class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    moogold_id = Column(Integer, unique=True, nullable=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    icon = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    moogold_id = Column(Integer, unique=True, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    availability_status = Column(String(30), default="available", nullable=False)

    # Provider integration
    provider = Column(String(32), default="manual")
    provider_product_id = Column(String(128), nullable=True)
    provider_meta = Column(JSONB, default=dict)

    # Dynamic order form requirements. These make regions/IDs configurable per product,
    # so MLBB, PUBG, Free Fire, Telegram Stars, etc. can each show only the fields they need.
    target_type = Column(String(30), default="game_id")  # game_id, telegram_username, none
    requires_target_id = Column(Boolean, default=True)
    requires_server_id = Column(Boolean, default=False)
    requires_region = Column(Boolean, default=False)
    target_id_label = Column(String(100), default="User ID / Game ID")
    target_server_label = Column(String(100), default="Server ID")
    target_region_label = Column(String(100), default="Region")
    region_options = Column(Text, nullable=True)  # JSON list: [{"code":"uz_global","label":"🇺🇿 UZB / 🌐 Global"}]
    input_help_text = Column(Text, nullable=True)
    
    category = relationship("Category", back_populates="products")
    variations = relationship("ProductVariation", back_populates="product")


class ProductVariation(Base):
    __tablename__ = "product_variations"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    moogold_variation_id = Column(Integer, unique=True, nullable=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=True)
    cost_currency = Column(String(10), default="UZS")
    stock_status = Column(String(20), default="instock")  # instock, outofstock
    image_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    availability_status = Column(String(30), default="available", nullable=False)

    # Provider integration
    provider = Column(String(32), default="manual")
    provider_variation_id = Column(String(128), nullable=True)
    provider_price = Column(Float, nullable=True)
    provider_currency = Column(String(16), nullable=True)
    provider_meta = Column(JSONB, default=dict)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('price >= 0', name='check_price_non_negative'),
    )
    
    product = relationship("Product", back_populates="variations")
    order_items = relationship("OrderItem", back_populates="variation")


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="created", index=True)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    
    # Payment info
    payment_method = Column(String(50), nullable=True)
    payment_amount = Column(Float, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    
    # MooGold
    moogold_order_id = Column(String(50), nullable=True)
    partner_order_id = Column(String(100), nullable=True)

    # Provider integration
    provider = Column(String(32), nullable=True)
    provider_order_id = Column(String(128), nullable=True)
    provider_status = Column(String(64), nullable=True)
    provider_response = Column(JSONB, default=dict)
    verified_target_name = Column(String(255), nullable=True)
    verified_target_payload = Column(JSONB, default=dict)
    
    # Target account info
    target_id = Column(String(255), nullable=True)
    target_server = Column(String(255), nullable=True)
    target_region = Column(String(100), nullable=True)
    target_region_label = Column(String(150), nullable=True)
    
    # Promo
    promo_code = Column(String(50), nullable=True)
    discount_amount = Column(Float, default=0.0)
    promo_usage_counted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    
    # Constraints
    __table_args__ = (
        CheckConstraint('total_amount >= 0', name='check_total_amount_non_negative'),
        CheckConstraint('payment_amount >= 0', name='check_payment_amount_non_negative'),
        CheckConstraint('discount_amount >= 0', name='check_discount_non_negative'),
    )
    
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    transactions = relationship("Transaction", back_populates="order")
    p2p_sessions = relationship("P2PPaymentSession", back_populates="order")
    moogold_fulfillments = relationship("MooGoldFulfillment", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    variation_id = Column(Integer, ForeignKey("product_variations.id"), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
        CheckConstraint('unit_price >= 0', name='check_unit_price_non_negative'),
        CheckConstraint('total_price >= 0', name='check_total_price_non_negative'),
    )
    
    order = relationship("Order", back_populates="items")
    variation = relationship("ProductVariation", back_populates="order_items")
    moogold_fulfillments = relationship("MooGoldFulfillment", back_populates="order_item")


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(20), default="completed")
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    
    # Constraints
    __table_args__ = (
        CheckConstraint('amount >= 0', name='check_amount_non_negative'),
    )
    
    user = relationship("User", back_populates="transactions")
    order = relationship("Order", back_populates="transactions")


class PromoCode(Base):
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    type = Column(String(20), nullable=False)
    value = Column(Float, nullable=False)
    min_order_amount = Column(Float, default=0.0)
    max_discount = Column(Float, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('value >= 0', name='check_value_non_negative'),
        CheckConstraint('min_order_amount >= 0', name='check_min_order_non_negative'),
        CheckConstraint('max_discount >= 0', name='check_max_discount_non_negative'),
        CheckConstraint('usage_limit >= 0', name='check_usage_limit_non_negative'),
    )


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    details = Column(Text, nullable=False)
    instructions = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    

class P2PCard(Base):
    """Payment card from the admin-managed P2P card pool."""
    __tablename__ = "p2p_cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    bank_name = Column(String(100), nullable=True)
    payment_system = Column(String(30), nullable=False, default="uzcard")  # uzcard, humo, visa, other
    card_number = Column(String(32), nullable=False)
    card_holder = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    last4 = Column(String(4), nullable=False, index=True)
    min_amount = Column(Float, default=0.0)
    max_amount = Column(Float, nullable=True)
    daily_limit = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    sessions = relationship("P2PPaymentSession", back_populates="card")
    balance_topups = relationship("BalanceTopUp", back_populates="card")

    __table_args__ = (
        CheckConstraint('min_amount >= 0', name='check_p2p_card_min_amount_non_negative'),
        CheckConstraint('max_amount >= 0', name='check_p2p_card_max_amount_non_negative'),
        CheckConstraint('daily_limit >= 0', name='check_p2p_card_daily_limit_non_negative'),
    )


class P2PPaymentSession(Base):
    """A concrete payment attempt: one order gets one card, exact amount and expiration time."""
    __tablename__ = "p2p_payment_sessions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("p2p_cards.id"), nullable=False, index=True)
    base_amount = Column(Float, nullable=False)
    unique_amount = Column(Float, nullable=False)
    assigned_amount = Column(Float, nullable=False, index=True)
    status = Column(String(20), default="active", index=True)  # active, paid, expired, cancelled
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    paid_at = Column(DateTime, nullable=True)
    incoming_payment_id = Column(Integer, ForeignKey("p2p_incoming_payments.id"), nullable=True)
    note = Column(Text, nullable=True)

    order = relationship("Order", back_populates="p2p_sessions")
    card = relationship("P2PCard", back_populates="sessions")
    incoming_payment = relationship("P2PIncomingPayment", foreign_keys=[incoming_payment_id])

    __table_args__ = (
        CheckConstraint('base_amount >= 0', name='check_p2p_base_amount_non_negative'),
        CheckConstraint('unique_amount >= 0', name='check_p2p_unique_amount_non_negative'),
        CheckConstraint('assigned_amount >= 0', name='check_p2p_assigned_amount_non_negative'),
        Index('idx_p2p_session_active_amount', 'status', 'assigned_amount'),
    )


class P2PIncomingPayment(Base):
    """Raw incoming bank/bot notification used by the auto parser."""
    __tablename__ = "p2p_incoming_payments"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(100), nullable=False, default="manual")
    raw_text = Column(Text, nullable=False)
    amount = Column(Float, nullable=True, index=True)
    currency = Column(String(10), default="UZS")
    card_last4 = Column(String(4), nullable=True, index=True)
    external_id = Column(String(120), nullable=True, unique=True)
    paid_at = Column(DateTime, nullable=True)
    matched_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    matched_session_id = Column(Integer, ForeignKey("p2p_payment_sessions.id"), nullable=True)
    matched_topup_id = Column(Integer, ForeignKey("balance_topups.id"), nullable=True)
    matched_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="new", index=True)  # new, matched, duplicate, unmatched, ignored, error, needs_review
    parser_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    matched_order = relationship("Order", foreign_keys=[matched_order_id])
    matched_session = relationship("P2PPaymentSession", foreign_keys=[matched_session_id])
    matched_topup = relationship("BalanceTopUp", foreign_keys=[matched_topup_id])
    matched_user = relationship("User", foreign_keys=[matched_user_id])


class BalanceTopUp(Base):
    """A balance top-up request that locks one P2P card for one user.

    This is the safer wallet flow requested for the shop:
    one active top-up = one reserved card = no unique amount required.
    """
    __tablename__ = "balance_topups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("p2p_cards.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="UZS")
    status = Column(String(20), default="pending", index=True)  # pending, paid, expired, needs_review, cancelled
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    paid_at = Column(DateTime, nullable=True)
    incoming_payment_id = Column(Integer, ForeignKey("p2p_incoming_payments.id"), nullable=True)
    note = Column(Text, nullable=True)

    user = relationship("User", back_populates="balance_topups")
    card = relationship("P2PCard", back_populates="balance_topups")
    incoming_payment = relationship("P2PIncomingPayment", foreign_keys=[incoming_payment_id])

    __table_args__ = (
        CheckConstraint('amount > 0', name='check_balance_topup_amount_positive'),
        Index('idx_balance_topups_active_card', 'status', 'card_id'),
    )


class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

class MooGoldFulfillment(Base):
    """One MooGold order created for one local order item.

    A local order can contain several items, while MooGold creates one order per
    product variation. This table keeps a safe mapping from local order/item to
    MooGold order id and makes webhook handling idempotent.
    """
    __tablename__ = "moogold_fulfillments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False, index=True)
    moogold_order_id = Column(String(100), unique=True, nullable=True, index=True)
    partner_order_id = Column(String(150), unique=True, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued", index=True)  # queued, processing, completed, refunded, cancelled, failed
    request_payload = Column(Text, nullable=True)
    response_payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    order = relationship("Order", back_populates="moogold_fulfillments")
    order_item = relationship("OrderItem", back_populates="moogold_fulfillments")

