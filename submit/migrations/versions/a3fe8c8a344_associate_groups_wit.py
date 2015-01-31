"""Associate groups with files.

Revision ID: a3fe8c8a344
Revises: 525162a280bd
Create Date: 2013-11-05 13:55:04.498181

"""

# revision identifiers, used by Alembic.
revision = 'a3fe8c8a344'
down_revision = '525162a280bd'

from alembic import op
from collections import defaultdict
from sqlalchemy.sql import table, column
import sqlalchemy as sa


submission = table('submission',
                   column('group_id', sa.Integer),
                   column('id', sa.Integer))

subtofile = table('submissiontofile',
                  column('file_id', sa.Integer),
                  column('submission_id'))

usertofile = table('user_to_file',
                   column('user_id', sa.Integer),
                   column('file_id', sa.Integer))

usertogroup = table('user_to_group',
                    column('group_id', sa.Integer),
                    column('user_id', sa.Integer))



def upgrade():
    conn = op.get_bind()
    group_files = defaultdict(set)
    group_users = defaultdict(list)
    sub_to_group = {}
    to_add = set()
    user_files = defaultdict(set)


    # Fetch mapping of users to files
    for (user_id, file_id) in conn.execute(usertofile.select()):
        user_files[user_id].add(file_id)

    # Fetch mapping of groups to users
    for (group_id, user_id) in conn.execute(usertogroup.select()):
        group_users[group_id].append(user_id)

    # Fetch mapping of submissions to groups
    for (group_id, sub_id) in conn.execute(submission.select()):
        sub_to_group[sub_id] = group_id

    # Build mapping of groups to files
    for (file_id, sub_id) in conn.execute(subtofile.select()):
        group_files[sub_to_group[sub_id]].add(file_id)

    # Build set of user to file associations to add
    for group_id, files in group_files.items():
        for user_id in group_users[group_id]:
            for file_id in files - user_files[user_id]:
                to_add.add((user_id, file_id))
    if to_add:
        op.bulk_insert(usertofile,
                       [{'user_id': x[0], 'file_id': x[1]} for x in to_add])


def downgrade():
    pass
