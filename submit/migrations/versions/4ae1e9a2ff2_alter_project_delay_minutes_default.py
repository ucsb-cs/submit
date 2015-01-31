"""Alter project delay_minutes default

Revision ID: 4ae1e9a2ff2
Revises: 38b07be99394
Create Date: 2014-04-22 16:58:18.218479

"""

# revision identifiers, used by Alembic.
revision = '4ae1e9a2ff2'
down_revision = '38b07be99394'

from alembic import op
import sqlalchemy as sa

project = sa.sql.table('project', sa.Column('delay_minutes', sa.Integer()))


def upgrade():
    op.alter_column('project', 'delay_minutes', server_default='1')
    op.execute(project.update().where(project.c.delay_minutes == 0)
               .values(delay_minutes=1))


def downgrade():
    op.alter_column('project', 'delay_minutes', server_default='0')
