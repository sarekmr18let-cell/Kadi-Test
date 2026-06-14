"""product requirements and regions

Revision ID: 005_product_requirements_regions
Revises: 004_wallet_balance_topups
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa


revision = "005_product_requirements_regions"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("target_type", sa.String(length=30), nullable=False, server_default="game_id"))
    op.add_column("products", sa.Column("requires_target_id", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("products", sa.Column("requires_server_id", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("products", sa.Column("requires_region", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("products", sa.Column("target_id_label", sa.String(length=100), nullable=False, server_default="User ID / Game ID"))
    op.add_column("products", sa.Column("target_server_label", sa.String(length=100), nullable=False, server_default="Server ID"))
    op.add_column("products", sa.Column("target_region_label", sa.String(length=100), nullable=False, server_default="Region"))
    op.add_column("products", sa.Column("region_options", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("input_help_text", sa.Text(), nullable=True))

    op.add_column("orders", sa.Column("target_region", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("target_region_label", sa.String(length=150), nullable=True))

    # Remove server defaults so app-level defaults stay in SQLAlchemy/Pydantic.
    op.alter_column("products", "target_type", server_default=None)
    op.alter_column("products", "requires_target_id", server_default=None)
    op.alter_column("products", "requires_server_id", server_default=None)
    op.alter_column("products", "requires_region", server_default=None)
    op.alter_column("products", "target_id_label", server_default=None)
    op.alter_column("products", "target_server_label", server_default=None)
    op.alter_column("products", "target_region_label", server_default=None)


def downgrade() -> None:
    op.drop_column("orders", "target_region_label")
    op.drop_column("orders", "target_region")

    op.drop_column("products", "input_help_text")
    op.drop_column("products", "region_options")
    op.drop_column("products", "target_region_label")
    op.drop_column("products", "target_server_label")
    op.drop_column("products", "target_id_label")
    op.drop_column("products", "requires_region")
    op.drop_column("products", "requires_server_id")
    op.drop_column("products", "requires_target_id")
    op.drop_column("products", "target_type")
