"""Add output_limit_exceeded to TCR.status enum.

Revision ID: 4f99b161d06c
Revises: 592873dff501
Create Date: 2013-02-12 17:00:33.069428

"""

# revision identifiers, used by Alembic.
revision = '4f99b161d06c'
down_revision = '592873dff501'

from alembic import op
import sqlalchemy as sa

old_options = ('nonexistent_executable', 'signal', 'success', 'timed_out')
new_options = sorted(old_options + ('output_limit_exceeded',))

old_type = sa.Enum(*old_options, name='status')
new_type = sa.Enum(*new_options, name='status')
tmp_type = sa.Enum(*new_options, name='_status')

tcr = sa.sql.table('testcaseresult',
                   sa.Column('status', new_type, nullable=False))


def upgrade():
    # Create a tempoary "_status" type, convert and drop the "old" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE testcaseresult ALTER COLUMN status TYPE _status'
               ' USING status::text::_status');
    old_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "new" status type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE testcaseresult ALTER COLUMN status TYPE status'
               ' USING status::text::status');
    tmp_type.drop(op.get_bind(), checkfirst=False)


def downgrade():
    # Convert 'output_limit_exceeded' status into 'timed_out'
    op.execute(tcr.update().where(tcr.c.status==u'output_limit_exceeded')
               .values(status='timed_out'))
    # Create a tempoary "_status" type, convert and drop the "new" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE testcaseresult ALTER COLUMN status TYPE _status'
               ' USING status::text::_status');
    new_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "old" status type
    old_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE testcaseresult ALTER COLUMN status TYPE status'
               ' USING status::text::status');
    tmp_type.drop(op.get_bind(), checkfirst=False)
