"""Add the shared user language.

Revision ID: 009_user_language_code
Revises: 008_product_availability_status
"""

from alembic import op
import sqlalchemy as sa


revision = "009_user_language_code"
down_revision = "008_product_availability_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "language_code",
            sa.String(length=5),
            server_default="ru",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_language_code",
        "users",
        "language_code IN ('ru', 'uz', 'en')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_language_code",
        "users",
        type_="check",
    )
    op.drop_column("users", "language_code")
