"""Give many-to-many tables a private key.

Revision ID: 385c579612dd
Revises: 49bc0cea7873
Create Date: 2013-09-13 16:54:23.776612

"""

# revision identifiers, used by Alembic.
revision = '385c579612dd'
down_revision = '49bc0cea7873'

from alembic import op
import sqlalchemy as sa

DESCRIPTIONS = [
        ('testable_to_build_file', ['testable_id', 'build_file_id']),
        ('testable_to_execution_file', ['testable_id', 'execution_file_id']),
        ('testable_to_file_verifier', ['testable_id', 'file_verifier_id']),
        ('user_to_class', ['user_id', 'class_id']),
        ('user_to_class_admin', ['user_id', 'class_id']),
        ('user_to_file', ['user_id', 'file_id'])]


def upgrade():
    for table, columns in DESCRIPTIONS:
        op.execute("""CREATE TEMPORARY TABLE tmp_{table} ON COMMIT DROP AS
                      SELECT DISTINCT * FROM {table};
                      truncate {table};
                      insert into {table} select * from tmp_{table};"""
                   .format(table=table))
        op.create_primary_key('{}_pkey'.format(table), table, columns)


def downgrade():
    for table, _ in DESCRIPTIONS:
        op.drop_constraint('{}_pkey'.format(table), table)
