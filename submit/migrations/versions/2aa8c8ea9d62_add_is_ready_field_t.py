"""Add is_ready field to Project.

Revision ID: 2aa8c8ea9d62
Revises: 4f99b161d06c
Create Date: 2013-02-13 11:22:37.123917

"""

# revision identifiers, used by Alembic.
revision = '2aa8c8ea9d62'
down_revision = '4f99b161d06c'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.schema import DefaultClause
from sqlalchemy.dialects import postgresql

project = sa.sql.table('project', sa.Column('is_ready', sa.Boolean(),
                                            nullable=True))


def upgrade():
    # Add is ready
    op.add_column('project', sa.Column('is_ready', sa.Boolean(),
                                       nullable=True))
    op.execute(project.update().values(is_ready=True))

    # Update nullability
    op.alter_column(u'project', u'is_ready', existing_type=sa.Boolean(),
                    nullable=False)
    op.alter_column(u'testcaseresult', u'status',
               existing_type=postgresql.ENUM(u'nonexistent_executable', u'output_limit_exceeded', u'signal', u'success', u'timed_out', name=u'status'),
               nullable=False)


def downgrade():
    # Remove column
    op.drop_column('project', 'is_ready')
    # Revert nullability of testcaseresult
    op.alter_column(u'testcaseresult', u'status',
               existing_type=postgresql.ENUM(u'nonexistent_executable', u'output_limit_exceeded', u'signal', u'success', u'timed_out', name=u'status'),
               nullable=True)
