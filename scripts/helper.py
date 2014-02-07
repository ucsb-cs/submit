#!/usr/bin/env python
from nudibranch.models import Session, Submission
import ldap
import sys

ATTRS = ('cn', 'sn', 'mail', 'uid', 'givenname', 'initials')


def fetch_name(ldap_conn, umail):
    def extract(item):
        if len(data[item]) == 1:
            return data[item][0]
        raise Exception('Multiple values returned')
    uid = umail.split('@')[0]
    results = ldap_conn.search_s('o=ucsb', ldap.SCOPE_ONELEVEL, attrlist=ATTRS,
                                 filterstr='uid={}'.format(uid))
    if len(results) != 1:
        return None
    data = results[0][1]
    if 'initials' in data:
        fullname = '{} {} {}'.format(extract('givenname'), extract('initials'),
                                     extract('sn'))
    else:
        fullname = extract('cn')
    return fullname


def connect():
    l = ldap.initialize('ldaps://directory.ucsb.edu')
    l.protocol_version = ldap.VERSION3
    return l


def merge_users(merge_to, merge_from):
    """Merge a non-umail account with a umail account."""
    # Determine most active user based on most recently created group
    assert(merge_to.username.endswith('umail.ucsb.edu'))

    # Merge groups
    for u2g in merge_from.groups_assocs[:]:
        merge_to.group_with(merge_from, u2g.project, bypass_limit=True)

    # merge classes and files
    merge_to.classes.extend(merge_from.classes)
    merge_to.files.extend(merge_from.files)

    # update file ownership
    for sub in Submission.query_by(created_by=merge_from).all():
        sub.created_by = merge_to

    # Delete the secondary user
    Session.delete(merge_from)


def main():
    pass

if __name__ == '__main__':
    sys.exit(main())
