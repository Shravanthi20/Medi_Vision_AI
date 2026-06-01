"""add face detection models

Revision ID: 937df8029ff5
Revises: e37895a1a06d
Create Date: 2026-05-10 22:26:59.403528

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '937df8029ff5'
down_revision = 'e37895a1a06d'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def upgrade():
    # ai_face_logs is already created by init_db migration (d580376bcbea).
    # Only add columns to customers that may not yet exist.
    if not _column_exists('customers', 'face_image_url'):
        op.add_column('customers', sa.Column('face_image_url', sa.Text(), nullable=True))
    if not _column_exists('customers', 'face_embedding'):
        op.add_column('customers', sa.Column('face_embedding', sa.JSON(), nullable=True))
    if not _column_exists('customers', 'last_face_scan_at'):
        op.add_column('customers', sa.Column('last_face_scan_at', sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c['name'] for c in insp.get_columns('customers')]
    with op.batch_alter_table('customers', schema=None) as batch_op:
        if 'last_face_scan_at' in cols:
            batch_op.drop_column('last_face_scan_at')
        if 'face_embedding' in cols:
            batch_op.drop_column('face_embedding')
        if 'face_image_url' in cols:
            batch_op.drop_column('face_image_url')

