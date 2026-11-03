"""Global display unit; a null unit means canonical grams."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    op.create_table("display_settings", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("default_unit_id", sa.Uuid(), sa.ForeignKey("unit.id")),
                    sa.CheckConstraint("id = 1"))
    op.execute("INSERT INTO display_settings (id) VALUES (1)")


def downgrade():
    op.drop_table("display_settings")
