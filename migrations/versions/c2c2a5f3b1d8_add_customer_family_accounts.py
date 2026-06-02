"""add customer family accounts

Revision ID: c2c2a5f3b1d8
Revises: 9f4a1b2c3d4e
Create Date: 2026-05-12 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2c2a5f3b1d8'
down_revision = '9f4a1b2c3d4e'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('customers')]
    if 'family_head_id' not in columns:
        op.add_column('customers', sa.Column('family_head_id', sa.Integer(), nullable=True))
    if 'family_relation' not in columns:
        op.add_column('customers', sa.Column('family_relation', sa.String(length=50), nullable=True))
    
    # Check foreign keys to see if the foreign key exists
    fks = inspector.get_foreign_keys('customers')
    fk_names = [fk['name'] for fk in fks if fk['name']]
    if 'fk_customers_family_head_id_customers' not in fk_names:
        op.create_foreign_key(
            'fk_customers_family_head_id_customers',
            'customers',
            'customers',
            ['family_head_id'],
            ['customer_id'],
        )


def downgrade():
    op.drop_constraint('fk_customers_family_head_id_customers', 'customers', type_='foreignkey')
    op.drop_column('customers', 'family_relation')
    op.drop_column('customers', 'family_head_id')
