"""Add title and user face embedding

Revision ID: 65fd014a1755
Revises: 28575d290353
Create Date: 2026-05-13 13:56:34.579400

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '65fd014a1755'
down_revision = '28575d290353'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(length=10), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('face_embedding', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('last_face_scan_at', sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_face_scan_at')
        batch_op.drop_column('face_embedding')
        batch_op.drop_column('title')

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('title')
