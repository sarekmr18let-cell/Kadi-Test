"""Add wallet balance top-ups with one-card lock

Revision ID: 004
Revises: 003
Create Date: 2026-06-13 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "balance_topups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=True, server_default="UZS"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("incoming_payment_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("amount > 0", name="check_balance_topup_amount_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["p2p_cards.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["incoming_payment_id"], ["p2p_incoming_payments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_balance_topups_id", "balance_topups", ["id"])
    op.create_index("ix_balance_topups_user_id", "balance_topups", ["user_id"])
    op.create_index("ix_balance_topups_card_id", "balance_topups", ["card_id"])
    op.create_index("ix_balance_topups_status", "balance_topups", ["status"])
    op.create_index("ix_balance_topups_expires_at", "balance_topups", ["expires_at"])
    op.create_index("idx_balance_topups_active_card", "balance_topups", ["status", "card_id"])

    op.add_column("p2p_incoming_payments", sa.Column("matched_topup_id", sa.Integer(), nullable=True))
    op.add_column("p2p_incoming_payments", sa.Column("matched_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_p2p_incoming_matched_topup_id",
        "p2p_incoming_payments",
        "balance_topups",
        ["matched_topup_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_p2p_incoming_matched_user_id",
        "p2p_incoming_payments",
        "users",
        ["matched_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_p2p_incoming_matched_user_id", "p2p_incoming_payments", type_="foreignkey")
    op.drop_constraint("fk_p2p_incoming_matched_topup_id", "p2p_incoming_payments", type_="foreignkey")
    op.drop_column("p2p_incoming_payments", "matched_user_id")
    op.drop_column("p2p_incoming_payments", "matched_topup_id")
    op.drop_table("balance_topups")
