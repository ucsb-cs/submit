"""Use email as username.

Revision ID: 124fff07cbcb
Revises: 133e975c3ad7
Create Date: 2013-01-29 23:57:33.083378

"""

# revision identifiers, used by Alembic.
revision = '124fff07cbcb'
down_revision = '133e975c3ad7'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

user = sa.sql.table('user',
                    sa.Column(u'email', sa.Unicode),
                    sa.Column(u'username', sa.Unicode))


def upgrade():
    op.execute(user.update().where(user.c.username!=u'admin')
               .values(username=user.c.email))
    op.drop_column('user', u'email')


def downgrade():
    op.add_column('user', sa.Column(u'email', sa.Unicode, nullable=True))
    op.execute(user.update().values(email=user.c.username))
    op.alter_column('user', u'email', nullable=False)
