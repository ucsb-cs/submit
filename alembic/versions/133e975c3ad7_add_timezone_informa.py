"""Add timezone information to datetime.

Revision ID: 133e975c3ad7
Revises: 2afd7cb1c8b7
Create Date: 2013-01-29 16:23:10.656380

"""

# revision identifiers, used by Alembic.
revision = '133e975c3ad7'
down_revision = '2afd7cb1c8b7'

from alembic import op
import sqlalchemy as sa

TABLES = ('buildfile', 'class', 'executionfile', 'file', 'fileverifier',
          'project', 'submission', 'testable', 'testcase', 'user')

def upgrade():
    for table in TABLES:
        op.alter_column(table, u'created_at', type_=sa.DateTime(timezone=True))
    op.alter_column('submission', u'made_at', type_=sa.DateTime(timezone=True))
    op.alter_column('submission', u'verified_at',
                    type_=sa.DateTime(timezone=True))


def downgrade():
    for table in TABLES:
        op.alter_column(table, u'created_at',
                        type_=sa.DateTime(timezone=False))
    op.alter_column('submission', u'made_at',
                    type_=sa.DateTime(timezone=False))
    op.alter_column('submission', u'verified_at',
                    type_=sa.DateTime(timezone=False))
