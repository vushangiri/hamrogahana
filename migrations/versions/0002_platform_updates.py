"""Rates, contacts and notification inbox."""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None

def upgrade():
    op.add_column("store", sa.Column("email", sa.String(254)))
    op.add_column("store", sa.Column("whatsapp", sa.String(20)))
    op.add_column("rate", sa.Column("effective_date", sa.Date()))
    op.add_column("rate", sa.Column("source", sa.String(20), nullable=False, server_default="manual"))
    op.add_column("rate", sa.Column("per_ten_grams", sa.Numeric(18,4)))
    op.add_column("rate", sa.Column("per_tola", sa.Numeric(18,4)))
    op.execute("UPDATE rate SET effective_date = (updated_at AT TIME ZONE 'Asia/Kathmandu')::date")
    op.create_table("rate_sync", sa.Column("day", sa.Date(), primary_key=True), sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("notification", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False), sa.Column("message", sa.String(500), nullable=False), sa.Column("href", sa.String(500), nullable=False), sa.Column("read_at", sa.DateTime(timezone=True)))
    op.create_index("ix_notification_user_id", "notification", ["user_id"])

def downgrade():
    op.drop_table("notification")
    op.drop_table("rate_sync")
    for name in ("effective_date", "source", "per_ten_grams", "per_tola"):
        op.drop_column("rate", name)
    op.drop_column("store", "email")
    op.drop_column("store", "whatsapp")
