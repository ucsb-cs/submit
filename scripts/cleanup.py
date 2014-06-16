#!/usr/bin/env python
from nudibranch.models import Class, Session, User
from pyramid.paster import get_appsettings, setup_logging
from sqlalchemy import engine_from_config, not_
import os
import sys
import transaction
import helper


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: {} <config_uri>\n'
          '(example: "{} development.ini")'.format(cmd, cmd))
    sys.exit(1)


def prompt(msg):
    sys.stdout.write('{} [(y)es, (N)o , (a)bort]: '.format(msg))
    sys.stdout.flush()
    value = sys.stdin.readline().strip().lower()
    if value in ('a', 'abort'):
        raise Exception('Prompt not accepted.')
    return value in ('y', 'yes', '1')


def locked_classes():
    for class_ in Class.query_by().order_by(Class.name.desc()).all():
        if class_.is_locked:
            yield class_


def delete_inactive_users():
    # Delete inactive users
    for user in User.query_by().order_by(User.created_at).all():
        msg = None
        if user.is_admin or len(user.admin_for) > 0:
            continue  # Admin for a class
        if not user.classes:
            msg = 'Delete user {} with no classes ({} files)'.format(
                user.name, len(user.files))
        elif not user.groups_assocs:
            msg = 'Delete user {} with no groups?'.format(user.name)
        elif not user.files:
            msg = 'Delete user {} with no files?'.format(user.name)
        if msg and prompt(msg):
            Session.delete(user)
    transaction.commit()


def update_umail_users():
    ldap_conn = helper.connect()
    for user in User.query_by().order_by(User.name).all():
        email = user.username
        if email.endswith('umail.ucsb.edu'):
            name = helper.fetch_name(ldap_conn, email)
            if name and name != user.name:
                user.name = name
            elif not name:
                print email, user.name
    transaction.commit()


def match_to_umail():
    ldap_conn = helper.connect()
    for user in sorted(
        User.query_by().filter(
            not_(User.username.contains('@umail.ucsb.edu'))).all()):
        if user.admin_for or user.is_admin or '(' in user.name:
            continue
        match = helper.find_user(ldap_conn, user.name)
        if match:
            print match, user.username


def delete_inactive_classes():
    for class_ in locked_classes():
        msg = None
        if len(class_.users) < 10:
            msg = ('Delete class {} with only {} users?'
                   .format(class_.name, len(class_.users)))
        elif len(class_.admins) < 1:
            msg = 'Delete class {} with no admins?'.format(class_.name)
        elif len(class_.projects) < 1:
            msg = 'Delete class {} with no projects?'.format(class_.name)
        if msg and prompt(msg):
            Session.delete(class_)
    transaction.commit()


def delete_unused_projects():
    for class_ in locked_classes():
        for project in class_.projects:
            submitted = set()
            for group in project.groups:
                submitted |= set(list(group.users)) - set(class_.admins)
            if len(submitted) < 10 and prompt(
                'Do you want to delete project {}:{} with {} students?'
                .format(class_.name, project.name, len(submitted))):
                Session.delete(project)
    transaction.commit()


def main():
    if len(sys.argv) < 2:
        usage(sys.argv)
    config_uri = sys.argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session.configure(bind=engine)

    #delete_unused_projects()
    delete_inactive_classes()
    delete_inactive_users()


    if False:
        update_umail_users()
        match_to_umail()


if __name__ == '__main__':
    sys.exit(main())
