#!/usr/bin/env python
import getpass
import json
import requests
import sys
from argparse import ArgumentParser, FileType
from urllib.parse import urljoin


class Nudibranch(object):
    BASE_URL = 'https://borg.cs.ucsb.edu'
    PATHS = {'auth': 'session',
             'project_item': 'class/{class_name}/{project_id}'}

    @classmethod
    def url(cls, resource, **kwargs):
        return urljoin(cls.BASE_URL, cls.PATHS[resource]).format(**kwargs)

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
            assert len(data) == 0
            response = self.session.get(url)
        elif method == 'head':
            assert len(data) == 0
            response = self.session.head(url)
        else:
            response = getattr(self.session, method)(url, json.dumps(data),
                                                     verify=False)
        return response

    def submit(self, project, files):
        self.login()
        if not self.verify_access(project):
            print('You cannot submit `{0}`'.format(project))
            return 1
        # Submit each file and get submission id
        # Notify of completed submission
        return 0

    def verify_access(self, project):
        class_name, project_id = project.split(':')
        url = self.url('project_item', class_name=class_name,
                       project_id=project_id)
        print(url)
        response = self.request(url, 'HEAD')
        self.msg('Access test: {0}'.format(response.status_code))
        return response.status_code == 200


def main():
    parser = ArgumentParser()
    parser.add_argument('-p', '--project', required=True)
    parser.add_argument('files', nargs='+', type=FileType())
    args = parser.parse_args()

    client = Nudibranch()
    return client.submit(args.project, args.files)

    return 0

if __name__ == '__main__':
    sys.exit(main())
