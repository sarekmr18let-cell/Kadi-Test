"""add user language code

Revision ID: 009_user_language_code
Revises: 008_product_availability_status
Create Date: 2026-06-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "009_user_language_code"
down_revision = "008_product_availability_status"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "ck_users_language_code_allowed"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "language_code",
            sa.String(length=5),
            nullable=False,
            server_default="ru",
        ),
    )
    op.execute("UPDATE users SET language_code = 'ru' WHERE language_code IS NULL")
    op.create_check_constraint(
        CONSTRAINT_NAME,
        "users",
        "language_code IN ('ru', 'uz', 'en')",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "users", type_="check")
    op.drop_column("users", "language_code")
