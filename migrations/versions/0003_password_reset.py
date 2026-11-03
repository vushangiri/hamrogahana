"""Manual password recovery requests, one pending request per phone."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "password_reset",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("store_name", sa.String(150), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.CheckConstraint("status IN ('pending','approved','rejected')"),
    )
    op.create_index("ix_password_reset_pending_phone", "password_reset", ["phone"], unique=True, postgresql_where=sa.text("status = 'pending'"))


def downgrade():
    op.drop_table("password_reset")
