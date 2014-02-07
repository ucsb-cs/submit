#!/usr/bin/env python
from nudibranch.models import User, Session
from pyramid_mailer.mailer import Mailer
from pyramid_mailer.message import Message
from pyramid.paster import get_appsettings, setup_logging
from sqlalchemy import engine_from_config
import os
import sys
import transaction
import fetch_by_umail as fbu

FORM_URL = 'https://docs.google.com/forms/d/1fG1ffEb0g9GjTkcKeJhC3amqeBYfBHkoZfpefmDK2eg/viewform?entry.832712741&entry.1138258707={email}'


SUBJECT = 'submit.cs account update'
BODY = """{name},

You are being emailed because you have an account on https://submit.cs.ucsb.edu
with the email {email}. We are in the process of requiring all account emails
to be umail accounts. Please complete the brief form at the following link so
we can perform this update:

{url}

If you have already registered a submit.cs account with your umail address,
please still complete the form so we can merge those accounts.

Thank you,
Bryce Boe
"""


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: {} <config_uri>\n'
          '(example: "{} development.ini")'.format(cmd, cmd))
    sys.exit(1)

def send_non_umail_form(mailer):
    ldap_conn = fbu.connect()
    for user in User.query_by().order_by(User.name).all():
        email = user.username
        if '@' not in email:
            print 'Invalid email: {}'.format(user)
        elif email != email.lower():
            print 'Non-lowercase email: {}'.format(user)
        elif not email.endswith('umail.ucsb.edu'):
            if user.admin_for:
                print 'Skipping: {}'.format(user)
                continue

            url = FORM_URL.format(email=user.username)
            body = BODY.format(name=user.name, email=user.username, url=url)
            to = '{} <{}>'.format(user.name, user.username)
            message = Message(subject=SUBJECT, body=body, recipients=[to])
            print to
            #mailer.send_immediately(message)

def main():
    if len(sys.argv) < 2:
        usage(sys.argv)
    config_uri = sys.argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session.configure(bind=engine)
    send_non_umail_form(Mailer.from_settings(settings))

if __name__ == '__main__':
    sys.exit(main())
