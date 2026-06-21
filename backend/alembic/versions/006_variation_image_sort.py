"""add variation image and sort order

Revision ID: 006_variation_image_sort
Revises: 005_product_requirements_regions
Create Date: 2026-06-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "006_variation_image_sort"
down_revision = "005_product_requirements_regions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_variations", sa.Column("image_url", sa.String(length=500), nullable=True))
    op.add_column(
        "product_variations",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.alter_column("product_variations", "sort_order", server_default=None)


def downgrade() -> None:
    op.drop_column("product_variations", "sort_order")
    op.drop_column("product_variations", "image_url")
