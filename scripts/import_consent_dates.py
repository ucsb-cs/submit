#!/usr/bin/env python
from submit.models import User, Session
from pyramid.paster import get_appsettings, setup_logging
from sqlalchemy import engine_from_config
from datetime import datetime
import os
import pytz
import sys
import transaction

TZ = pytz.timezone('America/Los_Angeles')


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: {} <config_uri> <consent_csv_uri>\n'
          '(example: "{} development.ini consent_csv")'.format(cmd, cmd))
    sys.exit(1)


def to_date(user):
    return datetime.strptime(user['consent_date'], '%m/%d/%Y').replace(
        tzinfo=TZ)


def fetch_consent_data(filename):
    people = []
    with open(filename) as fp:
        for i, line in enumerate(fp):
            if i == 0:
                continue
            _, last, first, email, cdate, _, _, _ = line.split(',')
            people.append({'last': last.strip().lower(),
                           'first': first.strip().lower(),
                           'email': email.strip().lower(),
                           'consent_date': cdate})
    return people


def main():
    if len(sys.argv) != 3:
        usage(sys.argv)
    config_uri = sys.argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session.configure(bind=engine)

    people = fetch_consent_data(sys.argv[2])
    by_email = {}
    for user in people:
        email = user['email']
        if email in by_email:
            if to_date(user) > by_email[email]:
                continue
        by_email[email] = to_date(user)
    matched = {}
    total = len(by_email)

    # Attempt to match by email
    for user in User.query_by().order_by(User.name).all():
        if user.username in by_email:
            matched[user.username] = by_email[user.username]
            if not user.consent_at or \
                    by_email[user.username] < user.consent_at:
                print 'updating'
                user.consent_at = by_email[user.username]
            del by_email[user.username]
    transaction.commit()
    print('Matched {} out of {} ({} remaining)'
          .format(len(matched), total, len(by_email)))


if __name__ == '__main__':
    sys.exit(main())
