"""Add is_locked attribute to Class.

Revision ID: 2aa111418585
Revises: 157166237cc7
Create Date: 2013-04-16 00:34:33.563294

"""

# revision identifiers, used by Alembic.
revision = '2aa111418585'
down_revision = '157166237cc7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('class', sa.Column('is_locked', sa.Boolean(),
                                     server_default=u'0', nullable=False))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('class', 'is_locked')
    ### end Alembic commands ###
