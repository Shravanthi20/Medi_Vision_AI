"""merge migration branches

Revision ID: 43bdada2911f
Revises: 65fd014a1755, d966ac1cd6fe
Create Date: 2026-05-15 15:48:37.105087

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43bdada2911f'
down_revision = ('65fd014a1755', 'd966ac1cd6fe')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
