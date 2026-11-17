"""Separate metal surplus and fixed-price products."""
from alembic import op
import sqlalchemy as sa
revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None

def upgrade():
    op.execute("INSERT INTO unit (id, name, symbol, grams, active, description, updated_at, created_at) SELECT gen_random_uuid(), 'Tola', 'tola', 11.6638, true, 'Nepal Tola', now(), now() WHERE NOT EXISTS (SELECT 1 FROM unit WHERE name = 'Tola' OR symbol = 'tola')")
    op.execute("UPDATE display_settings SET default_unit_id = (SELECT id FROM unit WHERE name = 'Tola' OR symbol = 'tola' ORDER BY name LIMIT 1) WHERE id = 1")
    op.execute("UPDATE rate SET value = round(per_tola / 11.6638, 4), per_ten_grams = NULL WHERE source = 'fenegosida' AND per_tola IS NOT NULL")
    op.add_column("product", sa.Column("weight_unit", sa.String(4), nullable=False, server_default="gram"))
    op.add_column("store", sa.Column("silver_surplus", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.execute("UPDATE store SET silver_surplus = surplus")
    op.create_check_constraint("ck_store_silver_surplus", "store", "silver_surplus >= 0")
    op.drop_constraint("product_metal_fkey", "product", type_="foreignkey")
    op.create_check_constraint("ck_product_metal", "product", "metal IN ('Gold','Silver','Other')")

def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM product WHERE metal = 'Other') THEN RAISE EXCEPTION 'Remove or convert Other products before downgrading'; END IF; END $$")
    op.drop_constraint("ck_product_metal", "product", type_="check")
    op.create_foreign_key("product_metal_fkey", "product", "rate", ["metal"], ["metal"])
    op.drop_constraint("ck_store_silver_surplus", "store", type_="check")
    op.drop_column("store", "silver_surplus")
    op.drop_column("product", "weight_unit")
