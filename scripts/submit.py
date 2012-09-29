#!/usr/bin/env python
import getpass
import json
import requests
import sys
from argparse import ArgumentParser, FileType
from urllib.parse import urljoin

class Nudibranch(object):
    BASE_URL = 'https://borg.cs.ucsb.edu'
    PATHS = {'auth': 'session'}

    @classmethod
    def url(cls, resource, **kwargs):
        return urljoin(cls.BASE_URL, cls.PATHS[resource]).format(kwargs)

    def __init__(self):
        self.debug = True
        self.session = requests.session()

    def msg(self, message):
        """Output a debugging message."""
        if self.debug:
            print(message)

    def login(self, username=None, password=None):
        """Login to establish a valid session."""
        auth_url = self.url('auth')
        while True:
            if not username and not password:
                sys.stdout.write('Username: ')
                sys.stdout.flush()
                username = sys.stdin.readline().strip()
                password = getpass.getpass()
            response = self.request(auth_url, 'PUT', username=username,
                                    password=password)
            if response.status_code == 201:
                self.msg('logged in')
                break
            else:
                print(response.json['message'])
                username = password = None

    def request(self, url, method='get', **data):
        method = method.lower()
        if method == 'get':
            assert data is None
            response = self.session.get(url)
        else:
            response = getattr(self.session, method)(url, json.dumps(data),
                                                     verify=False)
        return response

def main():
    parser = ArgumentParser()
    parser.add_argument('-p', '--project', required=True)
    parser.add_argument('files', nargs='+', type=FileType())
    args = parser.parse_args()

    client = Nudibranch()
    client.login('admin', 'passwor')

    # Verify project authorization

    # Submit each file and get submission id

    # Notify of completed submission

    return 0

if __name__ == '__main__':
    sys.exit(main())
