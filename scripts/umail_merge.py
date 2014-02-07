#!/usr/bin/env python
from nudibranch.models import User, Session
from pyramid.paster import get_appsettings, setup_logging
from sqlalchemy import engine_from_config
import os
import sys
import transaction
import helper


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: {} <config_uri>\n'
          '(example: "{} development.ini")'.format(cmd, cmd))
    sys.exit(1)


def merge_to_umail(ldap_conn, umail, other):
    other_user = User.fetch_by(username=other)
    if not other_user:
        print('Invalid user: {}'.format(other))
        return

    name = helper.fetch_name(ldap_conn, umail)
    if not name:
        print('Invalid umail: {}'.format(umail))
        return

    umail_user = User.fetch_by(username=umail)
    if umail_user:
        print('Merging {} with {}'.format(other_user, umail_user))
        helper.merge_users(umail_user, other_user)
    else:
        print('Changing {} to {}'.format(other_user, umail))
        other_user.name = name
        other_user.username = umail



def main():
    if len(sys.argv) < 2:
        usage(sys.argv)
    config_uri = sys.argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session.configure(bind=engine)

    ldap_conn = helper.connect()
    for line in sys.stdin:
        merge_to_umail(ldap_conn, *line.strip().split())
    transaction.commit()


if __name__ == '__main__':
    sys.exit(main())
