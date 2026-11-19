"""Add optional email verification for customer accounts."""

from alembic import op
import sqlalchemy as sa

revision = "0002_email_verification"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "is_email_verified", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "users", sa.Column("email_verification_token_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_token_hash")
    op.drop_column("users", "is_email_verified")
