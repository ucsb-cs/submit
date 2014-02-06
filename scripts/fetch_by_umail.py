#!/usr/bin/env python
import ldap
import os
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

def main():
    for umail in ['bboe@umail.ucsb.edu', 'BBOE@umail.ucsb.edu']:
        print fetch_name(l, umail)


if __name__ == '__main__':
    sys.exit(main())
