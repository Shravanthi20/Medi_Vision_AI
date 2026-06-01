"""Add customer_purchase_pattern and wanted_list fields

Revision ID: d966ac1cd6fe
Revises: c2c2a5f3b1d8
Create Date: 2026-05-13 19:31:16.705817

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

# revision identifiers, used by Alembic.
revision = 'd966ac1cd6fe'
down_revision = 'c2c2a5f3b1d8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('customer_purchase_patterns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('item_id', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('total_quantity', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('avg_quantity', sa.Float(), nullable=False))
        batch_op.drop_constraint(batch_op.f('customer_purchase_patterns_customer_id_category_id_combinat_key'), type_='unique')
        batch_op.create_unique_constraint(None, ['customer_id', 'item_id', 'category_id', 'combination_id'])
        batch_op.create_foreign_key(None, 'items', ['item_id'], ['item_id'])

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('face_embedding')
        batch_op.add_column(sa.Column('face_embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('name',
               existing_type=sa.VARCHAR(length=150),
               type_=sa.String(length=100),
               existing_nullable=True)

    with op.batch_alter_table('wanted_list', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(None, 'customers', ['customer_id'], ['customer_id'])


def downgrade():
    with op.batch_alter_table('wanted_list', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('customer_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('name',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=150),
               existing_nullable=True)

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.alter_column('face_embedding',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=128),
               existing_nullable=True)

    with op.batch_alter_table('customer_purchase_patterns', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_unique_constraint(batch_op.f('customer_purchase_patterns_customer_id_category_id_combinat_key'), ['customer_id', 'category_id', 'combination_id'], postgresql_nulls_not_distinct=False)
        batch_op.drop_column('avg_quantity')
        batch_op.drop_column('total_quantity')
        batch_op.drop_column('item_id')
