"""add billing vouchers

Revision ID: 9f4a1b2c3d4e
Revises: e37895a1a06d
Create Date: 2026-05-12 13:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '9f4a1b2c3d4e'
down_revision = 'e37895a1a06d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'billing_vouchers',
        sa.Column('voucher_id', sa.Integer(), nullable=False),
        sa.Column('voucher_type', sa.String(length=30), nullable=False),
        sa.Column('voucher_no', sa.String(length=30), nullable=False),
        sa.Column('voucher_date', sa.Date(), nullable=False),
        sa.Column('account_date', sa.Date(), nullable=True),
        sa.Column('reference_no', sa.String(length=50), nullable=True),
        sa.Column('reference_date', sa.Date(), nullable=True),
        sa.Column('customer_code', sa.String(length=50), nullable=True),
        sa.Column('account_code', sa.String(length=50), nullable=True),
        sa.Column('account_name', sa.String(length=150), nullable=True),
        sa.Column('party_name', sa.String(length=150), nullable=True),
        sa.Column('payment_type', sa.String(length=50), nullable=True),
        sa.Column('bank_code', sa.String(length=50), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('linked_bill_id', sa.Integer(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('amount >= 0', name='billing_voucher_amount_non_negative'),
        sa.ForeignKeyConstraint(['linked_bill_id'], ['sales_bills.bill_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('voucher_id'),
        sa.UniqueConstraint('voucher_type', 'voucher_no', name='billing_voucher_type_no_unique'),
    )


def downgrade():
    op.drop_table('billing_vouchers')
