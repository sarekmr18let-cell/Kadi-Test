"""Initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(255), nullable=True),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('is_blocked', sa.Boolean(), default=False),
        sa.Column('balance', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('referrer_id', sa.Integer(), nullable=True),
        sa.Column('referral_code', sa.String(50), unique=True, nullable=True),
        sa.Column('referral_bonus_earned', sa.Float(), default=0.0),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id'),
        sa.UniqueConstraint('referral_code'),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_users_telegram_id', 'users', ['telegram_id'])
    
    # Categories
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('moogold_id', sa.Integer(), unique=True, nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), unique=True, nullable=False),
        sa.Column('icon', sa.String(500), nullable=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Products
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('moogold_id', sa.Integer(), unique=True, nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    )
    
    # Product Variations
    op.create_table(
        'product_variations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('moogold_variation_id', sa.Integer(), unique=True, nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('stock_status', sa.String(20), default='instock'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    )
    
    # Orders
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(50), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), default='created'),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(10), default='USD'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('payment_amount', sa.Float(), nullable=True),
        sa.Column('payment_receipt', sa.String(500), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('moogold_order_id', sa.String(50), nullable=True),
        sa.Column('partner_order_id', sa.String(100), nullable=True),
        sa.Column('target_id', sa.String(255), nullable=True),
        sa.Column('target_server', sa.String(255), nullable=True),
        sa.Column('promo_code', sa.String(50), nullable=True),
        sa.Column('discount_amount', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_orders_status', 'orders', ['status'])
    op.create_index('idx_orders_user_id', 'orders', ['user_id'])
    
    # Order Items
    op.create_table(
        'order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('variation_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variation_id'], ['product_variations.id'], ondelete='CASCADE'),
    )
    
    # Transactions
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(10), default='USD'),
        sa.Column('status', sa.String(20), default='completed'),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
    )
    
    # Promo Codes
    op.create_table(
        'promo_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('min_order_amount', sa.Float(), default=0.0),
        sa.Column('max_discount', sa.Float(), nullable=True),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), default=0),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    
    # Payment Methods
    op.create_table(
        'payment_methods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('details', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Settings
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(100), unique=True, nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    
    # Insert default payment methods
    op.execute("""
        INSERT INTO payment_methods (name, details, instructions, sort_order) VALUES
        ('Bank Transfer', 'Card: **** **** **** 1234\nName: GameShop Inc', 'Transfer exact amount. Include order number in description.', 1),
        ('Humo', 'Card: 9860 **** **** 1234\nName: GameShop Inc', 'Transfer exact amount. Include order number in description.', 2),
        ('Uzcard', 'Card: 8600 **** **** 1234\nName: GameShop Inc', 'Transfer exact amount. Include order number in description.', 3)
    """)


def downgrade() -> None:
    op.drop_table('transactions')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('product_variations')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('promo_codes')
    op.drop_table('payment_methods')
    op.drop_table('settings')
    op.drop_table('users')
