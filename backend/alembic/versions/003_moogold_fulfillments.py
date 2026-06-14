"""Add MooGold fulfillment mapping table

Revision ID: 003
Revises: 002
Create Date: 2026-06-13 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "moogold_fulfillments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("moogold_order_id", sa.String(100), nullable=True),
        sa.Column("partner_order_id", sa.String(150), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("request_payload", sa.Text(), nullable=True),
        sa.Column("response_payload", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("moogold_order_id"),
        sa.UniqueConstraint("partner_order_id"),
    )
    op.create_index("ix_moogold_fulfillments_id", "moogold_fulfillments", ["id"])
    op.create_index("ix_moogold_fulfillments_order_id", "moogold_fulfillments", ["order_id"])
    op.create_index("ix_moogold_fulfillments_order_item_id", "moogold_fulfillments", ["order_item_id"])
    op.create_index("ix_moogold_fulfillments_moogold_order_id", "moogold_fulfillments", ["moogold_order_id"])
    op.create_index("ix_moogold_fulfillments_partner_order_id", "moogold_fulfillments", ["partner_order_id"])
    op.create_index("ix_moogold_fulfillments_status", "moogold_fulfillments", ["status"])


def downgrade() -> None:
    op.drop_table("moogold_fulfillments")
