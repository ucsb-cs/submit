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
from argparse import Action, ArgumentParser, ArgumentTypeError
from collections import defaultdict
from urlparse import urljoin


class Synchronize(object):
    PATHS = {'auth':           'session',
             'file_item':      'file/{sha1sum}/_',
             'test_case':      'test_case',
             'test_case_item': 'test_case/{test_case_id}',
             'testable':       'testable',
             'project_info':   'project/{project_id}'}

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
        locations = [os.path.join(os.path.dirname(__file__), 'submit.ini'),
                     'submit.ini']
        if os_config_path is not None:
            locations.insert(1, os.path.join(os_config_path, 'submit.ini'))
        if not config.read(locations):
            raise Exception('No submit.ini found.')
        if not config.has_section(section) and section != 'DEFAULT':
            raise Exception('No section `{0}` found in submit.ini.'
                            .format(section))
        return dict(config.items(section))

    def __init__(self, config_section):
        config = self._get_config(config_section)
        self.debug = config['debug'].lower() in ('1', 'true', 'yes')
        self.request_delay = int(config['request_delay'])
        self.request_timeout = int(config['request_timeout'])
        self._url = config['url']
        self.session = requests.session()
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.email = None

    def create_testables(self, testables, project_info):
        """Return a mapping of testable to testable infos."""
        retval = {}
        for testable in testables:
            if testable in project_info['testables']:
                retval[testable] = project_info['testables'][testable]
            else:
                url = self.url('testable')
                response = self.request(url, 'PUT', name=testable,
                                        project_id=unicode(project_info['id']),
                                        executable='a.out')
                self.msg('Creating testable: {0}'.format(response.status_code))
                if response.status_code != 201:
                    raise Exception('Could not create testable {0}'
                                    .format(testable))
                retval[testable] = {'id': response.json()['testable_id'],
                                    'name': testable, 'test_cases': []}
        return retval

    def get_info(self, project_id):
        url = self.url('project_info', project_id=project_id)
        response = self.request(url, 'GET')
        self.msg('Fetching project info: {0}'.format(response.status_code))
        if response.status_code != 200:
            return None
        return response.json()

    def get_tests(self, testables):
        tests = {}
        for path in testables:
            testable = os.path.basename(path)
            tests[testable] = defaultdict(dict)
            for filename in sorted(os.listdir(path)):
                filepath = os.path.join(path, filename)
                test_name, ext = os.path.splitext(filename)
                tests[testable][test_name][ext[1:]] = open(filepath).read()

            for test_case, info in tests[testable].items():
                if 'args' not in info:
                    print('File {0}/{1}.args does not exist. Goodbye!'
                          .format(testable, test_case))
                    sys.exit(1)
                extra = set(info) - set(['args'])
                if len(extra) > 1:
                    print('Too many extensions ({0}) for {1}/{2}. Goodbye!'
                          .format(list(extra), testable, test_case))
                    sys.exit(1)
                info['source'] = list(extra)[0]
        return tests

    def login(self, email=None, password=None):
        """Login to establish a valid session."""
        auth_url = self.url('auth')
        while True:
            if not email and not password:
                sys.stdout.write('Email: ')
                sys.stdout.flush()
                email = sys.stdin.readline().strip()
                if not email:
                    print('Goodbye!')
                    sys.exit(1)
                password = getpass.getpass()
            response = self.request(auth_url, 'PUT', email=email,
                                    password=password)
            if response.status_code == 201:
                self.msg('logged in')
                self.email = email
                break
            else:
                print(response.json()['messages'])
                email = password = None

    def msg(self, message):
        """Output a debugging message."""
        if self.debug:
            print('\t' + message)

    def request(self, url, method='get', **kwargs):
        time.sleep(self.request_delay)
        data = json.dumps(kwargs) if kwargs else None
        retval = self.session.request(method, url, data=data, verify=False,
                                      timeout=self.request_timeout)
        # Handle outage issues
        if retval.status_code == 502:
            print('The submission site is unexpectedly down. Please email '
                  'submit@cs.ucsb.edu with the URL: {0}'.format(url))
            sys.exit(1)
        elif retval.status_code == 503:
            print('The submission site is temporarily down for maintenance. '
                  'Please try your submission again in a minute.')
            sys.exit(1)
        return retval

    def send_file(self, data):
        sha1sum = hashlib.sha1(data).hexdigest()
        url = self.url('file_item', sha1sum=sha1sum)

        # Have we already uploaded the file?
        response = self.request(url, 'INFO')
        self.msg('Test file: {0}'.format(response.status_code))
        if response.status_code == 200:
            return response.json()['file_id']
        # Upload the file
        response = self.request(url, 'PUT',
                                b64data=base64.b64encode(data).decode('ascii'))
        self.msg('Send file: {0}'.format(response.status_code))
        if response.status_code == 200:
            return response.json()['file_id']
        else:
            return None

    def synchronize(self, project, testables):
        tests = self.get_tests(testables)
        self.login()
        project_info = self.get_info(project)
        if not project_info:
            print('You cannot edit `{0}`'.format(project))
            return 1
        mapping = self.create_testables(tests.keys(), project_info)
        for testable, info in mapping.items():
            self.synchronize_test_cases(info['id'], tests[testable],
                                        info['test_cases'])
        return 0

    def synchronize_test_cases(self, testable_id, available, existing):
        for name in available:
            info = available[name]
            stdin_id, expected_id = self.upload_files(
                info.get('stdin'), info[info['source']])
            kwargs = {'name': name, 'args': info['args'], 'points': unicode(1),
                      'expected_id': unicode(expected_id),
                      'output_type': 'diff'}
            if stdin_id:
                kwargs['stdin_id'] = stdin_id
            if info['source'] in ('stdout', 'stderr'):
                kwargs['output_source'] = info['source']
            else:
                kwargs['output_source'] = 'file'
                kwargs['output_filename'] = info['source']

            if name not in existing:
                kwargs['testable_id'] = unicode(testable_id)
                url = self.url('test_case')
                method = 'PUT'
            else:
                url = self.url('test_case_item',
                               test_case_id=existing[name]['id'])
                method = 'POST'
            response = self.request(url, method, **kwargs)
            if response.status_code not in (200, 201):
                print('Error uploading {0}: {1}'
                      .format(name, response.json()['messages']))
                return 1
        return 0

    def upload_files(self, stdin, expected):
        stdin_id = self.send_file(stdin) if stdin else None
        expected_id = self.send_file(expected)
        return stdin_id, expected_id

    def url(self, resource, **kwargs):
        return urljoin(self._url, self.PATHS[resource]).format(**kwargs)


class readable_dir(Action):
    """Test for a readable directory.

    Source: http://stackoverflow.com/questions/11415570/directory-path-types

    """

    @staticmethod
    def check_folder(path):
        # Verify the folder exists and is readable
        if not os.path.isdir(path):
            raise ArgumentTypeError('readable_dir: {0} is not a valid path'
                                    .format(path))
        if not os.access(path, os.R_OK):
            raise ArgumentTypeError('readable_dir: {0} is not a readable '
                                    'directory'.format(path))

    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, list):
            for path in values:
                self.check_folder(path)
        else:
            self.check_folder(values)
        setattr(namespace, self.dest, values)


def main():
    parser = ArgumentParser()
    parser.add_argument('-c', '--config', default='DEFAULT')
    parser.add_argument('-p', '--project_id', required=True)
    parser.add_argument('testables', nargs='+', action=readable_dir)
    args = parser.parse_args()

    client = Synchronize(args.config)
    client.debug = True
    return client.synchronize(args.project_id, args.testables)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
