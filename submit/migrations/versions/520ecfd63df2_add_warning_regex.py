"""add_warning_regex

Revision ID: 520ecfd63df2
Revises: None
Create Date: 2013-01-25 15:19:38.185554

"""

# revision identifiers, used by Alembic.
revision = '520ecfd63df2'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('fileverifier', sa.Column('warning_regex', sa.Unicode()))

def downgrade():
    op.drop_column('fileverifier', 'warning_regex')
