#!/usr/bin/env python
from nudibranch.models import User, Session
from pyramid_mailer.mailer import Mailer
from pyramid_mailer.message import Message
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


def merge_to_umail(ldap_conn, mailer, umail, other):
    umail = umail.lower()
    other_user = User.fetch_by(username=other)
    if not other_user:
        print('Invalid user: {}'.format(other))
        return

    name = helper.fetch_name(ldap_conn, umail)
    if not name:
        print('Invalid umail: {}'.format(umail))
        return

    to = '{} <{}>'.format(name, other)
    umail_user = User.fetch_by(username=umail)
    if umail_user:
        print('Merging {} with {}'.format(other_user, umail_user))
        helper.merge_users(umail_user, other_user)
        subject = 'submit.cs accounts merged'
        body = ('Your submit.cs account {old} has been merged with the account'
                ' {umail}. You will need to use {umail} and its associated '
                'password to login.\n\nIf you need to reset your password '
                'visit: https://submit.cs.ucsb.edu/password_reset'
                .format(old=other, umail=umail))
    else:
        print('Changing {} to {}'.format(other_user, umail))
        subject = 'submit.cs account username changed'
        body = ('Your submit.cs account name has been changed to {umail}. '
                'You will need to use this email to login on the submission '
                'system.'.format(umail=umail))
        other_user.name = name
        other_user.username = umail
    if mailer:
        body += '\n\nThank you,\nBryce Boe'
        message = Message(subject=subject, body=body, recipients=[to])
        mailer.send_immediately(message)


def main():
    if len(sys.argv) < 2:
        usage(sys.argv)
    config_uri = sys.argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session.configure(bind=engine)

    mailer = Mailer.from_settings(settings)
    ldap_conn = helper.connect()
    for line in sys.stdin:
        merge_to_umail(ldap_conn, mailer, *line.strip().split())
    transaction.commit()


if __name__ == '__main__':
    sys.exit(main())
