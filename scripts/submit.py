#!/usr/bin/env python
import base64
import getpass
import hashlib
import json
import os
import requests
import sys
import time
from ConfigParser import ConfigParser
from argparse import ArgumentParser, FileType
from urlparse import urljoin


class Nudibranch(object):
    PATHS = {'auth':           'session',
             'file_item':      'file/{sha1sum}',
             'file_item_info': 'file/{sha1sum}/info',
             'project_item':   'class/{class_name}/{project_id}/{username}',
             'submission':     'submission'}

    @staticmethod
    def _get_config(section):
        config = ConfigParser()
        if 'APPDATA' in os.environ:  # Windows
            os_config_path = os.environ['APPDATA']
        elif 'XDG_CONFIG_HOME' in os.environ:  # Modern Linux
            os_config_path = os.environ['XDG_CONFIG_HOME']
        elif 'HOME' in os.environ:  # Legacy Linux
            os_config_path = os.path.join(os.environ['HOME'], '.config')
        else:
            os_config_path = None
        locations = ['nudibranch.ini']
        if os_config_path is not None:
            locations.insert(0, os.path.join(os_config_path, 'nudibranch.ini'))
        if not config.read(locations):
            raise Exception('No nudibranch.ini found.')
        if not config.has_section(section) and section != 'DEFAULT':
            raise Exception('No section `{0}` found in nudibranch.ini.'
                            .format(section))
        return dict(config.items(section))

    def __init__(self, config_section):
        config = self._get_config(config_section)
        self.debug = config['debug'].lower() in ('1', 'true', 'yes')
        self.request_delay = int(config['request_delay'])
        self.request_timeout = int(config['request_timeout'])
        self._url = config['url']
        self.session = requests.session()
        self.username = None

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
                self.username = username
                break
            else:
                print(response.json['message'])
                username = password = None

    def msg(self, message):
        """Output a debugging message."""
        if self.debug:
            print('\t' + message)

    def make_submission(self, project, file_mapping):
        _, project_id = project.split(':')
        file_ids = []
        filenames = []
        for file_id, filename in file_mapping:
            file_ids.append(str(file_id))
            filenames.append(filename)
        response = self.request(self.url('submission'), 'PUT',
                                project_id=project_id, file_ids=file_ids,
                                filenames=filenames)
        self.msg('Make submission: {0}'.format(response.status_code))
        if response.status_code == 201:
            url = urljoin(self._url, response.json['redir_location'])
            print('Submission successful')
            print('Results will be available at: {0}'.format(url))
            return 0
        return 3

    def request(self, url, method='get', **data):
        time.sleep(self.request_delay)
        args = (json.dumps(data),) if data else ()
        return getattr(self.session, method.lower())(
            url, *args, verify=False, timeout=self.request_timeout)

    def send_file(self, the_file):
        print('Sending {0}'.format(the_file.name))
        data = the_file.read()
        sha1sum = hashlib.sha1(data).hexdigest()
        test_url = self.url('file_item_info', sha1sum=sha1sum)
        upload_url = self.url('file_item', sha1sum=sha1sum)

        # Have we already uploaded the file?
        response = self.request(test_url, 'GET')
        self.msg('Test file: {0}'.format(response.status_code))
        if response.status_code == 200:
            return response.json['file_id']
        # Upload the file
        response = self.request(upload_url, 'PUT',
                                b64data=base64.b64encode(data).decode('ascii'))
        self.msg('Send file: {0}'.format(response.status_code))
        if response.status_code == 200:
            return response.json['file_id']
        else:
            return None

    def submit(self, project, files):
        self.login()
        if not self.verify_access(project):
            print('You cannot submit `{0}`'.format(project))
            return 1
        success = True
        file_mapping = []
        for the_file in files:
            file_id = self.send_file(the_file)
            if file_id is not None:
                file_mapping.append((file_id, the_file.name))
            else:
                success = False
        if not success:
            print('Submission aborted')
            return 2
        return self.make_submission(project, file_mapping)

    def url(self, resource, **kwargs):
        return urljoin(self._url, self.PATHS[resource]).format(**kwargs)

    def verify_access(self, project):
        class_name, project_id = project.split(':')
        url = self.url('project_item', 
                       class_name=class_name,
                       project_id=project_id,
                       username=self.username)
        response = self.request(url, 'HEAD')
        self.msg('Access test: {0}'.format(response.status_code))
        return response.status_code == 200


def main():
    parser = ArgumentParser()
    parser.add_argument('-c', '--config', default='DEFAULT')
    parser.add_argument('-p', '--project', required=True)
    parser.add_argument('files', nargs='+', type=FileType('rb'))
    args = parser.parse_args()

    client = Nudibranch(args.config)
    return client.submit(args.project, args.files)


if __name__ == '__main__':
    sys.exit(main())
