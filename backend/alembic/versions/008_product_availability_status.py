"""add product availability status

Revision ID: 008_product_availability_status
Revises: 007_variation_cost_margin
Create Date: 2026-06-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "008_product_availability_status"
down_revision = "007_variation_cost_margin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("availability_status", sa.String(length=30), nullable=False, server_default="available"),
    )
    op.alter_column("products", "availability_status", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "availability_status")
