from __future__ import unicode_literals
import sys
import transaction
import unittest
from chameleon.zpt.template import Macro
from mock import MagicMock
from nudibranch import add_routes
from nudibranch.models import (Class, File, FileVerifier, Project, Session,
                               Submission, SubmissionToFile, TestCase,
                               Testable, User, initialize_sql)
from pyramid import testing
from pyramid.httpexceptions import (HTTPBadRequest, HTTPConflict, HTTPCreated,
                                    HTTPForbidden, HTTPNotFound, HTTPOk)
from pyramid.url import route_path
from sqlalchemy import create_engine

# Configure text type
if sys.version_info < (3, 0):
    text_type = unicode
else:
    text_type = str

FILE_DIR = '/tmp/nudibranch_test'


def _init_testing_db():
    """Create an in-memory database for testing."""
    engine = create_engine('sqlite://')
    initialize_sql(engine)

    # Add an admin user, two users, and two classes
    admin = User(email='', name='admin', username='admin', password='password',
                 is_admin=True)
    user1 = User(email='', name='User 1', username='user1', password='pswd1')
    user2 = User(email='', name='User 2', username='user2', password='pswd2')
    user3 = User(email='', name='User 3', username='user3', password='pswd3')
    klass1 = Class(name='Class 1')
    klass2 = Class(name='Class 2')
    Session.add_all([admin, user1, user2, user3, klass1, klass2])
    Session.flush()

    # Add two projects associated with klass1
    project1 = Project(name='Project 1', klass=klass1)
    project2 = Project(name='Project 2', klass=klass1)
    Session.add_all([project1, project2])
    Session.flush()

    # Add two testables associated with project1
    testable1 = Testable(name='Testable 1', executable='a.out', make_target='',
                         project=project1)
    testable2 = Testable(name='Testable 2', executable='a.out',
                         project=project1)
    Session.add_all([testable1, testable2])
    Session.flush()

    # Add two files, and two file verifiers
    file1 = File(base_path=FILE_DIR, data=b'',
                 sha1='da39a3ee5e6b4b0d3255bfef95601890afd80709')
    file2 = File(base_path=FILE_DIR, data=b'all:\n\tls',
                 sha1='5a874c84b1abdd164ce1ac6cdaa901575d3d7612')
    filev1 = FileVerifier(filename='File 1', min_size=0, min_lines=0,
                          project=testable1.project)
    filev1.testables.append(testable1)
    filev2 = FileVerifier(filename='File 2', min_size=0, min_lines=0,
                          project=testable1.project)
    filev2.testables.append(testable1)
    Session.add_all([file1, file2, filev1, filev2])
    Session.flush()

    # Add two test cases
    test_case1 = TestCase(name='Test Case 1', args='a.out', points=1,
                          testable=testable1, expected=file2)
    test_case2 = TestCase(name='Test Case 2', args='a.out', points=1,
                          testable=testable1, expected=file2, stdin=file2)
    Session.add_all([test_case1, test_case2])
    Session.flush()

    # Make associatations
    admin.files.append(file2)
    user1.classes.append(klass1)
    user1.files.append(file1)
    user3.classes.append(klass1)
    project2.makefile = file2
    Session.add_all([admin, user1, user3, project2])
    Session.flush()

    # Make a submission
    submission = Submission(project_id=project1.id, user_id=user1.id)
    s2f = SubmissionToFile(filename='File 1', file=file1)
    submission.files.append(s2f)
    Session.add_all([submission, s2f])


class BaseAPITest(unittest.TestCase):
    """Base test class for all API method (or controller) tests."""

    def make_request(self, **kwargs):
        """Build the request object used in view tests."""
        kwargs.setdefault('user', None)
        request = testing.DummyRequest(**kwargs)
        return request

    def setUp(self):
        """Initialize the database and add routes."""
        self.config = testing.setUp(settings={'file_directory': FILE_DIR,
                                              'queue_server': 'badhost',
                                              'queue_verification': 'NA'})
        _init_testing_db()
        add_routes(self.config)

    def tearDown(self):
        """Destroy the session and end the pyramid testing."""
        testing.tearDown()
        transaction.abort()
        Session.remove()


class BasicTests(BaseAPITest):
    def test_site_layout_decorator(self):
        from nudibranch.views import home
        request = self.make_request()
        info = home(request)
        self.assertIsInstance(info['_LAYOUT'], Macro)
        self.assertRaises(ValueError, info['_S'], 'favicon.ico')

    def test_home(self):
        from nudibranch.views import home
        request = self.make_request()
        info = home(request)
        self.assertEqual('Home', info['page_title'])


class ClassTests(BaseAPITest):
    """The the API methods involved with modifying class information."""

    def test_class_create_duplicate_name(self):
        from nudibranch.views import class_create
        json_data = {'name': 'Class 1'}
        request = self.make_request(json_body=json_data)
        info = class_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Class \'Class 1\' already exists', info['message'])

    def test_class_create_invalid_name(self):
        from nudibranch.views import class_create
        json_data = {}
        for item in ['', 'a' * 2]:
            json_data['name'] = item
            request = self.make_request(json_body=json_data)
            info = class_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_class_create_no_params(self):
        from nudibranch.views import class_create
        request = self.make_request(json_body={})
        info = class_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_class_create_valid(self):
        from nudibranch.views import class_create
        json_data = {'name': 'Foobar'}
        request = self.make_request(json_body=json_data)
        info = class_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        self.assertEqual(route_path('class', request), info['redir_location'])
        name = json_data['name']
        klass = Class.fetch_by(name=name)
        self.assertEqual(json_data['name'], klass.name)

    def test_class_edit(self):
        from nudibranch.views import class_edit
        request = self.make_request()
        info = class_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create Class', info['page_title'])

    def test_class_list(self):
        from nudibranch.views import class_list
        request = self.make_request()
        info = class_list(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual(2, len(info['classes']))
        self.assertEqual('Class 1', info['classes'][0].name)

    def test_class_view(self):
        from nudibranch.views import class_view
        request = self.make_request(matchdict={'class_name': 'Class 1'})
        info = class_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Class 1', info['klass'].name)

    def test_class_view_invalid(self):
        from nudibranch.views import class_view
        request = self.make_request(matchdict={'class_name': 'Test Invalid'})
        info = class_view(request)
        self.assertIsInstance(info, HTTPNotFound)


class ClassJoinTests(BaseAPITest):
    """Test the API methods involved in joining a class."""
    @staticmethod
    def get_objects():
        return User.fetch_by(username='user1'), {}

    def test_invalid_class(self):
        from nudibranch.views import user_class_join
        user, json_data = self.get_objects()
        request = self.make_request(json_body=json_data, user=user,
                                    matchdict={'class_name': 'Test Invalid',
                                               'username': 'user1'})
        info = user_class_join(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid class', info['messages'])

    def test_invalid_user(self):
        from nudibranch.views import user_class_join
        user, json_data = self.get_objects()
        request = self.make_request(json_body=json_data, user=user,
                                    matchdict={'class_name': 'Class 1',
                                               'username': 'admin'})
        info = user_class_join(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid user', info['messages'])

    def test_valid(self):
        from nudibranch.views import user_class_join
        user, json_data = self.get_objects()
        request = self.make_request(json_body=json_data, user=user,
                                    matchdict={'class_name': 'Class 1',
                                               'username': 'user1'})
        info = user_class_join(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Class joined', info['message'])


class FileTests(BaseAPITest):
    @staticmethod
    def get_objects(data='', username='user1'):
        user = User.fetch_by(username=username)
        json_data = {'b64data': data}
        return user, json_data

    def test_create_sha1sum_mismatch(self):
        from nudibranch.views import file_create
        user, json_data = self.get_objects()
        request = self.make_request(user=user, json_body=json_data,
                                    matchdict={'sha1sum': 'a' * 40})
        info = file_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        msg = 'sha1sum does not match'
        self.assertEqual(msg, info['messages'][:len(msg)])

    def test_create_already_exists(self):
        from nudibranch.views import file_create
        user, json_data = self.get_objects()
        sha1sum = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        request = self.make_request(user=user, json_body=json_data,
                                    matchdict={'sha1sum': sha1sum})
        info = file_create(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        expected_file = File.fetch_by(sha1=sha1sum)
        self.assertEqual(expected_file.id, info['file_id'])

    def test_create_success(self):
        from nudibranch.views import file_create
        user, json_data = self.get_objects(data='aGVsbG8gd29ybGQK')
        sha1sum = '22596363b3de40b06f981fb85d82312e8c0ed511'
        request = self.make_request(user=user, json_body=json_data,
                                    matchdict={'sha1sum': sha1sum})
        info = file_create(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        expected_file = File.fetch_by(sha1=sha1sum)
        self.assertEqual(expected_file.id, info['file_id'])

    def test_view_invalid_sha1sum_too_small(self):
        from nudibranch.views import file_item_info
        user, _ = self.get_objects()
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': 'a' * 39})
        info = file_item_info(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid sha1sum', info['messages'])

    def test_view_invalid_sha1sum_too_big(self):
        from nudibranch.views import file_item_info
        user, _ = self.get_objects()
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': 'a' * 41})
        info = file_item_info(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid sha1sum', info['messages'])

    def test_info_file_not_found(self):
        from nudibranch.views import file_item_info
        user, _ = self.get_objects()
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': 'a' * 40})
        info = file_item_info(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_user_did_not_upload_file(self):
        from nudibranch.views import file_item_info
        user, _ = self.get_objects(username='user2')
        sha1sum = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': sha1sum})
        info = file_item_info(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_found(self):
        from nudibranch.views import file_item_info
        user, _ = self.get_objects()
        sha1sum = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': sha1sum})
        info = file_item_info(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        expected_file = File.fetch_by(sha1=sha1sum)
        self.assertEqual(expected_file.id, info['file_id'])


class FileVerifierTests(BaseAPITest):
    @staticmethod
    def get_objects(username='admin', **kwargs):
        user = User.fetch_by(username=username)
        project = Session.query(Project).first()
        json_data = {'filename': 'File 3', 'min_size': '0', 'min_lines': '0',
                     'project_id': text_type(project.id)}
        json_data.update(kwargs)
        return user, json_data

    @staticmethod
    def get_update_objects(**kwargs):
        file_verifier = Session.query(FileVerifier).first()
        json_data = {'filename': 'File 3', 'min_size': '0', 'min_lines': '0'}
        json_data.update(kwargs)
        return {'file_verifier_id': file_verifier.id}, json_data

    def test_create_invalid_duplicate_name(self):
        from nudibranch.views import file_verifier_create
        user, json_data = self.get_objects(filename='File 2')
        request = self.make_request(json_body=json_data, user=user)
        info = file_verifier_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('That filename already exists for the project',
                         info['message'])

    def test_create_invalid_lines(self):
        from nudibranch.views import file_verifier_create
        user, json_data = self.get_objects(min_lines='10', max_lines='9')
        request = self.make_request(json_body=json_data, user=user)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_lines cannot be > max_lines', info['messages'])

    def test_create_invalid_maxes(self):
        from nudibranch.views import file_verifier_create
        user, json_data = self.get_objects(max_lines='10', max_size='9')
        request = self.make_request(json_body=json_data, user=user)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('max_lines cannot be > max_size', info['messages'])

    def test_create_invalid_mins(self):
        from nudibranch.views import file_verifier_create
        _, json_data = self.get_objects(min_lines='1', min_size='0')
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_lines cannot be > min_size', info['messages'])

    def test_create_invalid_size(self):
        from nudibranch.views import file_verifier_create
        _, json_data = self.get_objects(min_size='10', max_size='9')
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_size cannot be > max_size', info['messages'])

    def test_create_no_params(self):
        from nudibranch.views import file_verifier_create
        request = self.make_request(json_body={})
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(4, len(info['messages']))

    def test_create_valid(self):
        from nudibranch.views import file_verifier_create
        user, json_data = self.get_objects()
        request = self.make_request(json_body=json_data, user=user)
        info = file_verifier_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        project = Session.query(Project).first()
        expected = route_path('project_edit', request,
                              class_name=project.klass.name,
                              project_id=project.id)
        self.assertEqual(expected, info['redir_location'])
        file_verifier = project.file_verifiers[-1]
        self.assertEqual(json_data['filename'], file_verifier.filename)

    def test_update_invalid_duplicate_name(self):
        from nudibranch.views import file_verifier_update
        matchdict, json_data = self.get_update_objects(filename='File 2')
        user = User.fetch_by(username='admin')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = file_verifier_update(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('That filename already exists for the project',
                         info['message'])

    def test_update_invalid_lines(self):
        from nudibranch.views import file_verifier_update
        matchdict, json_data = self.get_update_objects(min_lines='10',
                                                       max_lines='9')
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = file_verifier_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_lines cannot be > max_lines', info['messages'])

    def test_update_invalid_maxes(self):
        from nudibranch.views import file_verifier_update
        matchdict, json_data = self.get_update_objects(max_lines='10',
                                                       max_size='9')
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = file_verifier_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('max_lines cannot be > max_size', info['messages'])

    def test_update_invalid_mins(self):
        from nudibranch.views import file_verifier_update
        matchdict, json_data = self.get_update_objects(min_lines='1',
                                                       min_size='0')
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = file_verifier_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_lines cannot be > min_size', info['messages'])

    def test_update_invalid_size(self):
        from nudibranch.views import file_verifier_update
        matchdict, json_data = self.get_update_objects(min_size='10',
                                                       max_size='9')
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = file_verifier_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_size cannot be > max_size', info['messages'])

    def test_update_no_params(self):
        from nudibranch.views import file_verifier_update
        request = self.make_request(json_body={})
        info = file_verifier_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(3, len(info['messages']))

    def test_update_valid(self):
        from nudibranch.views import file_verifier_update
        matchdict, json_data = self.get_update_objects()
        user = User.fetch_by(username='admin')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = file_verifier_update(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('updated', info['message'])
        file_verifier = FileVerifier.fetch_by_id(matchdict['file_verifier_id'])
        self.assertEqual(json_data['filename'], file_verifier.filename)


class ProjectTests(BaseAPITest):
    @staticmethod
    def get_objects(username='admin', **kwargs):
        user = User.fetch_by(username=username)
        klass = Session.query(Class).first()
        json_data = {'name': 'Foobar', 'class_id': text_type(klass.id)}
        json_data.update(kwargs)
        return user, json_data

    @staticmethod
    def get_update_objects(username='admin', md_update=None,
                           first_project=True, **kwargs):
        if first_project:
            proj = Session.query(Project).first()
        else:
            proj = Session.query(Project).all()[1]
        matchdict = {'class_name': proj.klass.name, 'project_id': proj.id}
        json_data = {'name': 'Foobar'}
        if md_update:
            matchdict.update(md_update)
        json_data.update(kwargs)
        user = User.fetch_by(username=username)
        return user, matchdict, json_data

    @staticmethod
    def get_view_objects(username='user1', **kwargs):
        user = User.fetch_by(username=username)
        proj = Session.query(Project).first()
        matchdict = {'class_name': proj.klass.name, 'project_id': proj.id,
                     'username': user.username}
        matchdict.update(kwargs)
        return user, matchdict

    def test_create_invalid_duplicate_name(self):
        from nudibranch.views import project_create
        user, json_data = self.get_objects(name='Project 1')
        request = self.make_request(json_body=json_data, user=user)
        info = project_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Project name already exists for the class',
                         info['message'])

    def test_create_invalid_id_str(self):
        from nudibranch.views import project_create
        user, json_data = self.get_objects(class_id=1)
        request = self.make_request(json_body=json_data, user=user)
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))

    def test_create_invalid_id_value(self):
        from nudibranch.views import project_create
        user, json_data = self.get_objects(class_id='1337')
        request = self.make_request(json_body=json_data, user=user)
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid class_id', info['messages'])

    def test_create_invalid_makefile_id(self):
        from nudibranch.views import project_create
        user, json_data = self.get_objects(makefile_id='100')
        request = self.make_request(json_body=json_data, user=user)
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid makefile_id', info['messages'])

    def test_create_invalid_makefile_id_perms(self):
        from nudibranch.views import project_create
        user, json_data = self.get_objects(makefile_id='1')
        request = self.make_request(json_body=json_data, user=user)
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid makefile_id', info['messages'])

    def test_create_no_params(self):
        from nudibranch.views import project_create
        request = self.make_request(json_body={})
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(2, len(info['messages']))

    def test_create_valid(self):
        from nudibranch.views import project_create
        user, json_data = self.get_objects()
        request = self.make_request(json_body=json_data, user=user)
        info = project_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected_prefix = route_path('project_edit', request,
                                     class_name='Class 1', project_id=0)[:-1]
        self.assertTrue(info['redir_location'].startswith(expected_prefix))
        project_id = int(info['redir_location'].rsplit('/', 1)[1])
        project = Project.fetch_by_id(project_id)
        self.assertEqual(json_data['name'], project.name)

    def test_edit(self):
        from nudibranch.views import project_edit
        project = Session.query(Project).first()
        user = User.fetch_by(username='admin')
        request = self.make_request(matchdict={'project_id': project.id},
                                    user=user)
        info = project_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Edit Project', info['page_title'])
        self.assertEqual(project.klass.id, info['project'].klass.id)

    def test_new(self):
        from nudibranch.views import project_new
        klass = Session.query(Class).first()
        user = User.fetch_by(username='admin')
        request = self.make_request(matchdict={'class_name': klass.name},
                                    user=user)
        info = project_new(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create Project', info['page_title'])
        self.assertEqual(klass.id, info['project'].klass.id)

    def test_update_duplicate(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(name='Project 2')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Project name already exists for the class',
                         info['message'])

    def test_update_invalid_makefile_id(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(makefile_id='100')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid makefile_id', info['messages'])

    def test_update_invalid_makefile_id_perms(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(makefile_id='1')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid makefile_id', info['messages'])

    def test_update_invalid_product_id(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(
            {'project_id': 100})
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid project_id', info['messages'])

    def test_update_inconsistent_class_name(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(
            {'class_name': 'Invalid'})
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Inconsistent class specification', info['messages'])

    def test_update_no_change(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(name='Project 1')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Nothing to change', info['message'])

    def test_update_no_params(self):
        from nudibranch.views import project_update
        request = self.make_request(json_body={})
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))

    def test_update_valid_add_makefile(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(name='Project 1',
                                                             makefile_id='2')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        proj = Session.query(Project).first()
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project updated', info['message'])
        self.assertEqual(int(json_data['makefile_id']), proj.makefile_id)

    def test_update_valid_remove_makefile(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects(
            first_project=False, name='Project 2')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        proj = Session.query(Project).first()
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project updated', info['message'])
        self.assertEqual(None, proj.makefile)

    def test_update_valid_update_name(self):
        from nudibranch.views import project_update
        user, matchdict, json_data = self.get_update_objects()
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = project_update(request)
        proj = Session.query(Project).first()
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project updated', info['message'])
        self.assertEqual('Foobar', proj.name)

    def test_view_detailed(self):
        from nudibranch.views import project_view_detailed
        user, matchdict = self.get_view_objects()
        request = self.make_request(user=user, matchdict=matchdict)
        info = project_view_detailed(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project 1', info['project'].name)
        self.assertEqual('User 1', info['name'])

    def test_view_detailed_as_admin(self):
        from nudibranch.views import project_view_detailed
        user, matchdict = self.get_view_objects(username='admin')
        matchdict['username'] = 'user1'
        request = self.make_request(user=user, matchdict=matchdict)
        info = project_view_detailed(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project 1', info['project'].name)
        self.assertEqual('User 1', info['name'])

    def test_view_detailed_incorrect_class_name(self):
        from nudibranch.views import project_view_detailed
        user, matchdict = self.get_view_objects(class_name='Test Invalid')
        request = self.make_request(user=user, matchdict=matchdict)
        info = project_view_detailed(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_detailed_user_cannot_access_other_user_info(self):
        from nudibranch.views import project_view_detailed
        user, matchdict = self.get_view_objects()
        matchdict['username'] = 'user3'
        request = self.make_request(user=user, matchdict=matchdict)
        info = project_view_detailed(request)
        self.assertIsInstance(info, HTTPForbidden)

    def test_view_detailed_user_not_part_of_class(self):
        from nudibranch.views import project_view_detailed
        user, matchdict = self.get_view_objects(username='user2')
        request = self.make_request(user=user, matchdict=matchdict)
        info = project_view_detailed(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_detailed_invalid_id(self):
        from nudibranch.views import project_view_detailed
        user = User.fetch_by(username='user1')
        user, matchdict = self.get_view_objects(project_id='100')
        request = self.make_request(user=user, matchdict=matchdict)
        info = project_view_detailed(request)
        self.assertIsInstance(info, HTTPNotFound)


class SessionTests(BaseAPITest):
    """Test the API methods involved in session creation and destruction."""

    def test_session_create_invalid(self):
        from nudibranch.views import session_create
        request = self.make_request(json_body={'username': 'user1',
                                               'password': 'badpw'})
        info = session_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Invalid login', info['message'])

    def test_session_create_no_params(self):
        from nudibranch.views import session_create
        request = self.make_request(json_body={})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(2, len(info['messages']))

    def test_session_create_no_password(self):
        from nudibranch.views import session_create
        request = self.make_request(json_body={'username': 'foo'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_session_create_no_username(self):
        from nudibranch.views import session_create
        request = self.make_request(json_body={'password': 'bar'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_session_create_valid(self):
        from nudibranch.views import session_create
        request = self.make_request(json_body={'username': 'user1',
                                               'password': 'pswd1'})
        info = session_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        self.assertEqual(route_path('user_item', request, username='user1'),
                         info['redir_location'])

    def test_session_edit(self):
        from nudibranch.views import session_edit
        request = self.make_request()
        info = session_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Login', info['page_title'])


class SubmissionTests(BaseAPITest):
    """Test the API methods involved with Submissions."""
    @staticmethod
    def get_objects(**kwargs):
        user = User.fetch_by(username='user1')
        project = Session.query(Project).first()
        the_file = Session.query(File).first()
        json_data = {'file_ids': [text_type(the_file.id)],
                     'filenames': ['File 1'],
                     'project_id': text_type(project.id)}
        json_data.update(kwargs)
        return user, json_data

    def test_create_invalid_file(self):
        from nudibranch.views import submission_create
        user, json_data = self.get_objects(file_ids=['100'])
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))
        self.assertTrue(info['messages'][0].startswith('Invalid file'))

    def test_create_invalid_project(self):
        from nudibranch.views import submission_create
        user, json_data = self.get_objects(project_id='100')
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))
        self.assertEqual('Invalid project_id', info['messages'][0])

    def test_create_list_mismatch(self):
        from nudibranch.views import submission_create
        user, json_data = self.get_objects()
        json_data['file_ids'].append('1')
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))
        self.assertEqual('# file_ids must match # filenames',
                         info['messages'][0])

    def test_create_valid(self):
        import nudibranch.views
        nudibranch.views.pika = MagicMock()
        from nudibranch.views import submission_create
        user, json_data = self.get_objects()
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected_prefix = route_path('submission', request,
                                     submission_id=0)[:-1]
        self.assertTrue(info['redir_location'].startswith(expected_prefix))


class TestCaseTests(BaseAPITest):
    """Test the API methods involved with modifying test cases."""
    @staticmethod
    def get_objects(**kwargs):
        testable = Session.query(Testable).first()
        json_data = {'name': 'Test Case 3', 'args': 'test', 'points': '10',
                     'testable_id': text_type(testable.id), 'expected_id': '2'}
        json_data.update(kwargs)
        return json_data

    @staticmethod
    def get_update_objects(md_update=None, first_test_case=True, **kwargs):
        if first_test_case:
            test_case = Session.query(TestCase).first()
        else:
            test_case = Session.query(TestCase).all()[1]
        matchdict = {'test_case_id': test_case.id}
        json_data = {'name': 'Test Case 3', 'args': 'test', 'points': '10',
                     'expected_id': '2'}
        if md_update:
            matchdict.update(md_update)
        json_data.update(kwargs)
        return matchdict, json_data

    def test_create_invalid_duplicate_name(self):
        from nudibranch.views import test_case_create
        user = User.fetch_by(username='admin')
        json_data = self.get_objects(name='Test Case 1')
        request = self.make_request(json_body=json_data, user=user)
        info = test_case_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('That name already exists for the testable',
                         info['message'])

    def test_create_invalid_expected_id(self):
        from nudibranch.views import test_case_create
        user = User.fetch_by(username='admin')
        json_data = self.get_objects(expected_id='100')
        request = self.make_request(json_body=json_data, user=user)
        info = test_case_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid expected_id', info['messages'])

    def test_create_invalid_expected_id_perms(self):
        from nudibranch.views import test_case_create
        user = User.fetch_by(username='admin')
        json_data = self.get_objects(expected_id='1')
        request = self.make_request(json_body=json_data, user=user)
        info = test_case_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid expected_id', info['messages'])

    def test_create_invalid_stdin_id(self):
        from nudibranch.views import test_case_create
        user = User.fetch_by(username='admin')
        json_data = self.get_objects(stdin_id='100')
        request = self.make_request(json_body=json_data, user=user)
        info = test_case_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid stdin_id', info['messages'])

    def test_create_invalid_stdin_id_perms(self):
        from nudibranch.views import test_case_create
        user = User.fetch_by(username='admin')
        json_data = self.get_objects(stdin_id='1')
        request = self.make_request(json_body=json_data, user=user)
        info = test_case_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid stdin_id', info['messages'])

    def test_create_no_params(self):
        from nudibranch.views import test_case_create
        request = self.make_request(json_body={})
        info = test_case_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(5, len(info['messages']))

    def test_create_valid(self):
        from nudibranch.views import test_case_create
        user = User.fetch_by(username='admin')
        json_data = self.get_objects(stdin_id='2')
        request = self.make_request(json_body=json_data, user=user)
        info = test_case_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        testable = Session.query(Testable).first()
        expected = route_path('project_edit', request,
                              class_name=testable.project.klass.name,
                              project_id=testable.project.id)
        self.assertEqual(expected, info['redir_location'])
        test_case = testable.test_cases[-1]
        self.assertEqual(json_data['name'], test_case.name)
        self.assertEqual(int(json_data['expected_id']), test_case.expected_id)
        self.assertEqual(int(json_data['stdin_id']), test_case.stdin_id)

    def test_serialize(self):
        test_case = Session.query(TestCase).first()
        data = test_case.serialize()
        self.assertEqual(test_case.id, data['id'])
        self.assertEqual(test_case.args, data['args'])

    def test_update_invalid_duplicate_name(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(name='Test Case 2')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('That name already exists for the project',
                         info['message'])

    def test_update_invalid_expected_id(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(expected_id='100')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid expected_id', info['messages'])

    def test_update_invalid_expected_id_perms(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(expected_id='1')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid expected_id', info['messages'])

    def test_update_invalid_stdin_id(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(stdin_id='100')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid stdin_id', info['messages'])

    def test_update_invalid_stdin_id_perms(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(stdin_id='1')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid stdin_id', info['messages'])

    def test_update_no_params(self):
        from nudibranch.views import test_case_update
        request = self.make_request(json_body={})
        info = test_case_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(4, len(info['messages']))

    def test_update_no_change(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(args='a.out',
                                                       name='Test Case 1',
                                                       points='1')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Nothing to change', info['message'])

    def test_update_valid_add_stdin(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(stdin_id='2')
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Test case updated', info['message'])
        tc = TestCase.fetch_by_id(matchdict['test_case_id'])
        self.assertEqual(int(json_data['stdin_id']), tc.stdin_id)

    def test_update_valid_remove_stdin(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects(first_test_case=False)
        tc = TestCase.fetch_by_id(matchdict['test_case_id'])
        self.assertNotEqual(None, tc.stdin_id)
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Test case updated', info['message'])
        tc = TestCase.fetch_by_id(matchdict['test_case_id'])
        self.assertEqual(None, tc.stdin_id)

    def test_update_valid_update_attrs(self):
        from nudibranch.views import test_case_update
        user = User.fetch_by(username='admin')
        matchdict, json_data = self.get_update_objects()
        request = self.make_request(json_body=json_data, matchdict=matchdict,
                                    user=user)
        info = test_case_update(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Test case updated', info['message'])
        tc = TestCase.fetch_by_id(matchdict['test_case_id'])
        self.assertEqual(None, tc.stdin_id)
        self.assertEqual(json_data['args'], tc.args)
        self.assertEqual(json_data['name'], tc.name)
        self.assertEqual(int(json_data['points']), tc.points)


class UserTests(BaseAPITest):
    """Test the API methods involved with modifying user information."""
    @staticmethod
    def get_objects(**kwargs):
        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'password': 'Foobar', 'username': 'user0'}
        json_data.update(kwargs)
        return json_data

    def test_user_create_duplicate_name(self):
        from nudibranch.views import user_create
        json_data = self.get_objects(username='user1')
        request = self.make_request(json_body=json_data)
        info = user_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('User \'user1\' already exists', info['message'])

    def test_user_create_invalid_email(self):
        from nudibranch.views import user_create
        json_data = self.get_objects()
        for item in ['', 'a' * 5]:
            json_data['email'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_name(self):
        from nudibranch.views import user_create
        json_data = self.get_objects()
        for item in ['', 'a' * 2]:
            json_data['name'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_password(self):
        from nudibranch.views import user_create
        json_data = self.get_objects()
        for item in ['', 'a' * 5]:
            json_data['password'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_username(self):
        from nudibranch.views import user_create
        json_data = self.get_objects()
        for item in ['', 'a' * 2, 'a' * 17]:
            json_data['username'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_no_params(self):
        from nudibranch.views import user_create
        request = self.make_request(json_body={})
        info = user_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(4, len(info['messages']))

    def test_user_create_valid(self):
        from nudibranch.views import user_create
        json_data = self.get_objects()
        request = self.make_request(json_body=json_data)
        info = user_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected = route_path('session', request, _query={'username': 'user0'})
        self.assertEqual(expected, info['redir_location'])
        username = json_data['username']
        user = User.fetch_by(username=username)
        self.assertEqual(json_data['email'], user.email)
        self.assertEqual(json_data['name'], user.name)
        self.assertNotEqual(json_data['password'], user._password)

    def test_user_edit(self):
        from nudibranch.views import user_edit
        request = self.make_request()
        info = user_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create User', info['page_title'])

    def test_user_list(self):
        from nudibranch.views import user_list
        request = self.make_request()
        info = user_list(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual(4, len(info['users']))
        self.assertEqual('user1', info['users'][1].username)

    def test_user_view(self):
        from nudibranch.views import user_view
        request = self.make_request(matchdict={'username': 'user1'})
        info = user_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('user1', info['user'].username)

    def test_user_view_invalid(self):
        from nudibranch.views import user_view
        request = self.make_request(matchdict={'username': 'Invalid'})
        info = user_view(request)
        self.assertIsInstance(info, HTTPNotFound)


### Non-view tests
class DummyTemplateTest(unittest.TestCase):
    def test_default_attribute_values(self):
        from nudibranch.views import DummyTemplateAttr
        a = DummyTemplateAttr()
        self.assertEqual(None, a.bar)
        self.assertEqual(None, a.foo)

    def test_explicit_default_attribute_values(self):
        from nudibranch.views import DummyTemplateAttr
        a = DummyTemplateAttr('a')
        self.assertEqual('a', a.bar)
        self.assertEqual('a', a.foo)

    def test_set_attribute(self):
        from nudibranch.views import DummyTemplateAttr
        a = DummyTemplateAttr()
        a.foo = 'foo'
        self.assertEqual(None, a.bar)
        self.assertEqual('foo', a.foo)


if __name__ == '__main__':
    unittest.main()
