"""add name and phone to users

Revision ID: e37895a1a06d
Revises: 084cd999da74
Create Date: 2026-05-06 23:42:15.804249

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e37895a1a06d'
down_revision = '084cd999da74'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to the users table
    op.add_column('users', sa.Column('name', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))

def downgrade():
    # Remove the columns if downgraded
    op.drop_column('users', 'phone')
    op.drop_column('users', 'name')
