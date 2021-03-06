"""Add TestableResult

Revision ID: 592873dff501
Revises: cd2ca183062
Create Date: 2013-01-30 11:52:02.023925

"""

# revision identifiers, used by Alembic.
revision = '592873dff501'
down_revision = 'cd2ca183062'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('testableresult',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('make_results', sa.UnicodeText(), nullable=True),
                    sa.Column('submission_id', sa.Integer(), nullable=False),
                    sa.Column('testable_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['submission_id'], [u'submission.id'], ),
                    sa.ForeignKeyConstraint(['testable_id'], [u'testable.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('submission_id','testable_id'))
    op.drop_column(u'submission', u'make_results')
    op.drop_column(u'submission', u'made_at')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column(u'submission', sa.Column(u'made_at', postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(u'submission', sa.Column(u'make_results', sa.TEXT(), nullable=True))
    op.drop_table('testableresult')
    ### end Alembic commands ###
