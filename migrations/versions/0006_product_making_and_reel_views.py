"""Support percentage making charges and weekly reel views."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.add_column("product", sa.Column("making_percentage", sa.Numeric(7, 4)))
    op.create_check_constraint(
        "ck_product_making_percentage", "product", "making_percentage BETWEEN 0 AND 100"
    )
    op.create_table(
        "reel_view",
        sa.Column("store_id", sa.Uuid, sa.ForeignKey("store.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_id", sa.Uuid, sa.ForeignKey("media.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewer_id", sa.Uuid, sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week", sa.Date, nullable=False),
        sa.PrimaryKeyConstraint("store_id", "week", "media_id", "viewer_id"),
    )


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM product WHERE making_percentage IS NOT NULL) THEN
                RAISE EXCEPTION 'Convert percentage-based making charges before downgrading';
            END IF;
        END $$
    """)
    op.drop_table("reel_view")
    op.drop_constraint("ck_product_making_percentage", "product", type_="check")
    op.drop_column("product", "making_percentage")
