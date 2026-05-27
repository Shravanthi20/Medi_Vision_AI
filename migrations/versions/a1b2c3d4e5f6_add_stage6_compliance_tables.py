"""Add Stage 6 compliance tables: expiry_returns, expiry_return_items, license_documents

Revision ID: a1b2c3d4e5f6
Revises: 9f4a1b2c3d4e
Create Date: 2026-05-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = '9f4a1b2c3d4e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('expiry_returns',
        sa.Column('expiry_return_id', sa.Integer(), nullable=False),
        sa.Column('return_no', sa.String(length=30), nullable=False),
        sa.Column('return_date', sa.Date(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('financial_year_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='DRAFT'),
        sa.Column('total_qty', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_value', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('credit_note_no', sa.String(length=50), nullable=True),
        sa.Column('credit_note_date', sa.Date(), nullable=True),
        sa.Column('credit_note_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('DRAFT','DISPATCHED','CREDIT_NOTE_RECEIVED','CLOSED')",
            name='expiry_return_status_check'
        ),
        sa.ForeignKeyConstraint(['financial_year_id'], ['financial_years.financial_year_id']),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.supplier_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('expiry_return_id'),
        sa.UniqueConstraint('return_no'),
    )

    op.create_table('expiry_return_items',
        sa.Column('expiry_return_item_id', sa.BigInteger(), nullable=False),
        sa.Column('expiry_return_id', sa.Integer(), nullable=False),
        sa.Column('stock_batch_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.String(length=10), nullable=False),
        sa.Column('batch_no', sa.String(length=30), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('qty_returned', sa.Integer(), nullable=False),
        sa.Column('purchase_rate', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('mrp', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('return_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('qty_returned > 0', name='expiry_return_qty_positive'),
        sa.ForeignKeyConstraint(['expiry_return_id'], ['expiry_returns.expiry_return_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.item_id']),
        sa.ForeignKeyConstraint(['stock_batch_id'], ['stock_batches.stock_batch_id']),
        sa.PrimaryKeyConstraint('expiry_return_item_id'),
    )

    op.create_table('license_documents',
        sa.Column('license_id', sa.Integer(), nullable=False),
        sa.Column('license_type', sa.String(length=50), nullable=False),
        sa.Column('license_name', sa.String(length=150), nullable=False),
        sa.Column('license_no', sa.String(length=100), nullable=False),
        sa.Column('issuing_authority', sa.String(length=150), nullable=True),
        sa.Column('issued_date', sa.Date(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('alert_90', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('alert_60', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('alert_30', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('doc_url', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('renewal_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('renewal_contact', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('license_id'),
    )

    # Index for fast expiry date queries
    op.create_index('ix_license_documents_expiry_date', 'license_documents', ['expiry_date'])
    op.create_index('ix_expiry_returns_status', 'expiry_returns', ['status'])
    op.create_index('ix_expiry_returns_supplier_id', 'expiry_returns', ['supplier_id'])


def downgrade():
    op.drop_index('ix_expiry_returns_supplier_id', table_name='expiry_returns')
    op.drop_index('ix_expiry_returns_status', table_name='expiry_returns')
    op.drop_index('ix_license_documents_expiry_date', table_name='license_documents')
    op.drop_table('expiry_return_items')
    op.drop_table('expiry_returns')
    op.drop_table('license_documents')
