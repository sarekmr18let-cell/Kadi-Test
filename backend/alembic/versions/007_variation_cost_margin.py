"""add variation cost price and currency

Revision ID: 007_variation_cost_margin
Revises: 006_variation_image_sort
Create Date: 2026-06-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "007_variation_cost_margin"
down_revision = "006_variation_image_sort"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_variations", sa.Column("cost_price", sa.Float(), nullable=True))
    op.add_column(
        "product_variations",
        sa.Column("cost_currency", sa.String(length=10), server_default="UZS", nullable=False),
    )
    op.alter_column("product_variations", "cost_currency", server_default=None)


def downgrade() -> None:
    op.drop_column("product_variations", "cost_currency")
    op.drop_column("product_variations", "cost_price")
