#!/usr/bin/env python
from nudibranch.models import User, Session
from pyramid.paster import get_appsettings, setup_logging
from sqlalchemy import engine_from_config
import os
import sys
import transaction
import fetch_by_umail as fbu


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: {} <config_uri>\n'
          '(example: "{} development.ini")'.format(cmd, cmd))
    sys.exit(1)


def delete_inactive_users(session):
    # Delete inactive users
    for user in User.query_by().order_by(User.created_at).all():
        if not user.files and not user.groups_assocs:
            Session.delete(user)
    transaction.commit()


def update_umail_users():
    ldap_conn = fbu.connect()
    for user in User.query_by().order_by(User.name).all():
        email = user.username
        if email.endswith('umail.ucsb.edu'):
            name = fbu.fetch_name(ldap_conn, email)
            if name and name != user.name:
                user.name = name
            elif not name:
                print email, user.name
    transaction.commit()


def main():
    if len(sys.argv) < 2:
        usage(sys.argv)
    config_uri = sys.argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session.configure(bind=engine)

    delete_inactive_users(Session)
    update_umail_users()
    return  # The following is not complete yet

    # Find users with the same name
    names = {}
    for user in User.query_by().order_by(User.name).all():
        name = user.name.lower()
        if name in names:
            print name, names[name]
            user.merge(names[name])
        names[name] = user

    transaction.commit()


if __name__ == '__main__':
    sys.exit(main())
