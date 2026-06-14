"""Add P2P card pool, payment sessions and incoming payment parser

Revision ID: 002
Revises: 001
Create Date: 2026-06-13 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('promo_usage_counted', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    op.create_table(
        'p2p_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('bank_name', sa.String(100), nullable=True),
        sa.Column('payment_system', sa.String(30), nullable=False, server_default='uzcard'),
        sa.Column('card_number', sa.String(32), nullable=False),
        sa.Column('card_holder', sa.String(255), nullable=True),
        sa.Column('phone_number', sa.String(50), nullable=True),
        sa.Column('last4', sa.String(4), nullable=False),
        sa.Column('min_amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('max_amount', sa.Float(), nullable=True),
        sa.Column('daily_limit', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint('min_amount >= 0', name='check_p2p_card_min_amount_non_negative'),
        sa.CheckConstraint('max_amount >= 0', name='check_p2p_card_max_amount_non_negative'),
        sa.CheckConstraint('daily_limit >= 0', name='check_p2p_card_daily_limit_non_negative'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_p2p_cards_id', 'p2p_cards', ['id'])
    op.create_index('ix_p2p_cards_last4', 'p2p_cards', ['last4'])
    op.create_index('ix_p2p_cards_is_active', 'p2p_cards', ['is_active'])

    op.create_table(
        'p2p_incoming_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(100), nullable=False, server_default='manual'),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True, server_default='UZS'),
        sa.Column('card_last4', sa.String(4), nullable=True),
        sa.Column('external_id', sa.String(120), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('matched_order_id', sa.Integer(), nullable=True),
        sa.Column('matched_session_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='new'),
        sa.Column('parser_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['matched_order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    )
    op.create_index('ix_p2p_incoming_payments_id', 'p2p_incoming_payments', ['id'])
    op.create_index('ix_p2p_incoming_payments_amount', 'p2p_incoming_payments', ['amount'])
    op.create_index('ix_p2p_incoming_payments_card_last4', 'p2p_incoming_payments', ['card_last4'])
    op.create_index('ix_p2p_incoming_payments_status', 'p2p_incoming_payments', ['status'])

    op.create_table(
        'p2p_payment_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('base_amount', sa.Float(), nullable=False),
        sa.Column('unique_amount', sa.Float(), nullable=False),
        sa.Column('assigned_amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('incoming_payment_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.CheckConstraint('base_amount >= 0', name='check_p2p_base_amount_non_negative'),
        sa.CheckConstraint('unique_amount >= 0', name='check_p2p_unique_amount_non_negative'),
        sa.CheckConstraint('assigned_amount >= 0', name='check_p2p_assigned_amount_non_negative'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['p2p_cards.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['incoming_payment_id'], ['p2p_incoming_payments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_p2p_payment_sessions_id', 'p2p_payment_sessions', ['id'])
    op.create_index('ix_p2p_payment_sessions_order_id', 'p2p_payment_sessions', ['order_id'])
    op.create_index('ix_p2p_payment_sessions_card_id', 'p2p_payment_sessions', ['card_id'])
    op.create_index('ix_p2p_payment_sessions_assigned_amount', 'p2p_payment_sessions', ['assigned_amount'])
    op.create_index('ix_p2p_payment_sessions_status', 'p2p_payment_sessions', ['status'])
    op.create_index('ix_p2p_payment_sessions_expires_at', 'p2p_payment_sessions', ['expires_at'])
    op.create_index('idx_p2p_session_active_amount', 'p2p_payment_sessions', ['status', 'assigned_amount'])

    # Add FK from incoming payments to sessions after sessions table exists.
    op.create_foreign_key(
        'fk_p2p_incoming_matched_session_id',
        'p2p_incoming_payments',
        'p2p_payment_sessions',
        ['matched_session_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_p2p_incoming_matched_session_id', 'p2p_incoming_payments', type_='foreignkey')
    op.drop_table('p2p_payment_sessions')
    op.drop_table('p2p_incoming_payments')
    op.drop_table('p2p_cards')
    op.drop_column('orders', 'promo_usage_counted')
