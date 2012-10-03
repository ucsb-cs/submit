import transaction
import unittest
from chameleon.zpt.template import Macro
from nudibranch import add_routes
from nudibranch.models import *
from nudibranch.views import *
from pyramid import testing
from pyramid.httpexceptions import (HTTPBadRequest, HTTPConflict, HTTPCreated,
                                    HTTPForbidden, HTTPNotFound, HTTPOk)
from pyramid.url import route_path
from sqlalchemy import create_engine

FILE_DIR = '/tmp/nudibranch_test'


def _init_testing_db():
    """Create an in-memory database for testing."""
    engine = create_engine('sqlite://')
    initialize_sql(engine)

    # Add a class
    klass = Class(name='Test 101')
    Session.add(klass)
    Session.flush()

    # Add two projects and a user associated with the class
    project = Project(name='Project 1', class_id=klass.id)
    user = User(email='', name='User', username='user1',
                password='pswd1', classes=[klass])
    Session.add_all([project, Project(name='Project 2', class_id=klass.id),
                     user])
    Session.flush()

    # Add a file verifier to the project
    Session.add(FileVerifier(filename='File 1', min_size=0, min_lines=0,
                             project_id=project.id))

    # Add a file to the system
    the_file = File(base_path=FILE_DIR, data=b'',
                    sha1='da39a3ee5e6b4b0d3255bfef95601890afd80709')
    Session.add(the_file)
    Session.flush()

    # Associate user and file
    user.files.append(the_file)
    Session.add(user)

    # Make a submission
    submission = Submission(project_id=project.id, user_id=user.id)
    s2f = SubmissionToFile(filename='File 1', the_file=the_file)
    submission.files.append(s2f)
    Session.add_all([submission, s2f])

    # Add a nonassociated user
    Session.add(User(email='', name='User', username='user2', password='0000'))


class BaseAPITest(unittest.TestCase):
    """Base test class for all API method (or controller) tests."""

    def make_request(self, **kwargs):
        """Build the request object used in view tests."""
        kwargs.setdefault('user', None)
        request = testing.DummyRequest(**kwargs)
        return request

    def setUp(self):
        """Initialize the database and add routes."""
        self.config = testing.setUp(settings={'file_directory': FILE_DIR})
        _init_testing_db()
        add_routes(self.config)

    def tearDown(self):
        """Destroy the session and end the pyramid testing."""
        testing.tearDown()
        transaction.abort()
        Session.remove()


class BasicTests(BaseAPITest):
    def test_site_layout_decorator(self):
        request = self.make_request()
        info = home(request)
        self.assertIsInstance(info['_LAYOUT'], Macro)
        self.assertRaises(ValueError, info['_S'], 'favicon.ico')

    def test_home(self):
        request = self.make_request()
        info = home(request)
        self.assertEqual('Home', info['page_title'])


class ClassTests(BaseAPITest):
    """The the API methods involved with modifying class information."""

    def test_class_create_duplicate_name(self):
        json_data = {'name': 'Test 101'}
        request = self.make_request(json_body=json_data)
        info = class_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Class \'Test 101\' already exists', info['message'])

    def test_class_create_invalid_name(self):
        json_data = {}
        for item in ['', 'a' * 2]:
            json_data['name'] = item
            request = self.make_request(json_body=json_data)
            info = class_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_class_create_no_params(self):
        request = self.make_request(json_body={})
        info = class_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_class_create_valid(self):
        json_data = {'name': 'Foobar'}
        request = self.make_request(json_body=json_data)
        info = class_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        self.assertEqual(route_path('class', request), info['redir_location'])
        name = json_data['name']
        klass = Session.query(Class).filter_by(name=name).first()
        self.assertEqual(json_data['name'], klass.name)

    def test_class_edit(self):
        request = self.make_request()
        info = class_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create Class', info['page_title'])

    def test_class_list(self):
        request = self.make_request()
        info = class_list(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual(1, len(info['classes']))
        self.assertEqual('Test 101', info['classes'][0].name)

    def test_class_view(self):
        request = self.make_request(matchdict={'class_name': 'Test 101'})
        info = class_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Test 101', info['klass'].name)

    def test_class_view_invalid(self):
        request = self.make_request(matchdict={'class_name': 'Test Invalid'})
        info = class_view(request)
        self.assertIsInstance(info, HTTPNotFound)


class ClassJoinTests(BaseAPITest):
    """Test the API methods involved in joining a class."""

    def test_invalid_class(self):
        user = Session.query(User).filter_by(username='user1').first()
        request = self.make_request(json_body={}, user=user,
                                    matchdict={'class_name': 'Test Invalid',
                                               'username': 'user1'})
        info = user_class_join(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid class', info['messages'])

    def test_invalid_user(self):
        user = Session.query(User).filter_by(username='user1').first()
        request = self.make_request(json_body={}, user=user,
                                    matchdict={'class_name': 'Test 101',
                                               'username': 'admin'})
        info = user_class_join(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid user', info['messages'])

    def test_valid(self):
        user = Session.query(User).filter_by(username='user1').first()
        request = self.make_request(json_body={}, user=user,
                                    matchdict={'class_name': 'Test 101',
                                               'username': 'user1'})
        info = user_class_join(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Class joined', info['message'])


class FileTests(BaseAPITest):
    def test_create_sha1sum_mismatch(self):
        user = Session.query(User).filter_by(username='user1').first()
        project = Session.query(Project).first()
        json_data = {'b64data': ''}
        request = self.make_request(user=user, json_body=json_data,
                                    matchdict={'sha1sum': 'a' * 40})
        info = file_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        msg = 'sha1sum does not match'
        self.assertEqual(msg, info['messages'][:len(msg)])

    def test_create_already_exists(self):
        user = Session.query(User).filter_by(username='user1').first()
        project = Session.query(Project).first()
        json_data = {'b64data': ''}
        sha1sum = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        request = self.make_request(user=user, json_body=json_data,
                                    matchdict={'sha1sum': sha1sum})
        info = file_create(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        expected_file = File.fetch_by_sha1(sha1sum)
        self.assertEqual(expected_file.id, info['file_id'])

    def test_create_success(self):
        user = Session.query(User).filter_by(username='user1').first()
        project = Session.query(Project).first()
        json_data = {'b64data': 'aGVsbG8gd29ybGQK'}
        sha1sum = '22596363b3de40b06f981fb85d82312e8c0ed511'
        request = self.make_request(user=user, json_body=json_data,
                                    matchdict={'sha1sum': sha1sum})
        info = file_create(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        expected_file = File.fetch_by_sha1(sha1sum)
        self.assertEqual(expected_file.id, info['file_id'])

    def test_view_invalid_sha1sum_too_small(self):
        user = Session.query(User).filter_by(username='user1').first()
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': 'a' * 39})
        info = file_view(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid sha1sum', info['messages'])

    def test_view_invalid_sha1sum_too_big(self):
        user = Session.query(User).filter_by(username='user1').first()
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': 'a' * 41})
        info = file_view(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid sha1sum', info['messages'])

    def test_view_file_not_found(self):
        user = Session.query(User).filter_by(username='user1').first()
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': 'a' * 40})
        info = file_view(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_user_did_not_upload_file(self):
        user = Session.query(User).filter_by(username='user2').first()
        sha1sum = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': sha1sum})
        info = file_view(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_found(self):
        user = Session.query(User).filter_by(username='user1').first()
        sha1sum = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        request = self.make_request(user=user,
                                    matchdict={'sha1sum': sha1sum})
        info = file_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        expected_file = File.fetch_by_sha1(sha1sum)
        self.assertEqual(expected_file.id, info['file_id'])


class FileVerifierTests(BaseAPITest):
    def test_create_invalid_duplicate_name(self):
        project = Session.query(Project).first()
        json_data = {'filename': 'File 1', 'min_size': '0', 'min_lines': '0',
                     'project_id': str(project.id)}
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('That filename already exists for the project',
                         info['message'])

    def test_create_invalid_lines(self):
        project = Session.query(Project).first()
        json_data = {'filename': 'File 1', 'min_lines': '10', 'max_lines': '9',
                     'min_size': '0', 'project_id': str(project.id)}
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_lines cannot be > max_lines', info['messages'])

    def test_create_invalid_maxes(self):
        project = Session.query(Project).first()
        json_data = {'filename': 'File 1', 'min_lines': '0', 'min_size': '0',
                     'max_lines': '10', 'max_size': '9',
                     'project_id': str(project.id)}
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('max_lines cannot be > max_size', info['messages'])

    def test_create_invalid_mins(self):
        project = Session.query(Project).first()
        json_data = {'filename': 'File 1', 'min_lines': '1', 'min_size': '0',
                     'project_id': str(project.id)}
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_lines cannot be > min_size', info['messages'])

    def test_create_invalid_size(self):
        project = Session.query(Project).first()
        json_data = {'filename': 'File 1', 'min_size': '10', 'max_size': '9',
                     'min_lines': '0', 'project_id': str(project.id)}
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('min_size cannot be > max_size', info['messages'])

    def test_create_no_params(self):
        request = self.make_request(json_body={})
        info = file_verifier_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(4, len(info['messages']))

    def test_create_valid(self):
        project = Session.query(Project).first()
        json_data = {'filename': 'File 2', 'min_size': '0', 'min_lines': '0',
                     'project_id': str(project.id)}
        request = self.make_request(json_body=json_data)
        info = file_verifier_create(request)

        project = Session.query(Project).first()
        expected = route_path('project_edit', request, project_id=project.id,
                              class_name=project.klass.name)
        self.assertEqual(expected, info['redir_location'])
        file_verifier = project.file_verifiers[-1]
        self.assertEqual(json_data['filename'], file_verifier.filename)


class ProjectTests(BaseAPITest):
    def test_create_invalid_duplicate_name(self):
        klass = Session.query(Class).first()
        json_data = {'name': 'Project 1', 'class_id': str(klass.id)}
        request = self.make_request(json_body=json_data)
        info = project_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Project name already exists for the class',
                         info['message'])

    def test_create_invalid_id_str(self):
        klass = Session.query(Class).first()
        json_data = {'name': 'Foobar', 'class_id': klass.id}
        request = self.make_request(json_body=json_data)
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))

    def test_create_invalid_id_value(self):
        json_data = {'name': 'Foobar', 'class_id': '1337'}
        request = self.make_request(json_body=json_data)
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid class_id', info['messages'])

    def test_create_no_params(self):
        request = self.make_request(json_body={})
        info = project_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(2, len(info['messages']))

    def test_create_valid(self):
        klass = Session.query(Class).first()
        class_name = klass.name
        json_data = {'name': 'Foobar', 'class_id': str(klass.id)}
        request = self.make_request(json_body=json_data)
        info = project_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected_prefix = route_path('project_edit', request,
                                     class_name=class_name, project_id=0)[:-1]
        self.assertTrue(info['redir_location'].startswith(expected_prefix))
        project_id = int(info['redir_location'].rsplit('/', 1)[1])
        project = Session.query(Project).filter_by(id=project_id).first()
        self.assertEqual(json_data['name'], project.name)

    def test_edit(self):
        project = Session.query(Project).first()
        request = self.make_request(matchdict={'project_id': project.id})
        info = project_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Edit Project', info['page_title'])
        self.assertEqual(project.klass.id, info['project'].klass.id)

    def test_new(self):
        klass = Session.query(Class).first()
        request = self.make_request(matchdict={'class_name': klass.name})
        info = project_new(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create Project', info['page_title'])
        self.assertEqual(klass.id, info['project'].klass.id)

    def test_update_duplicate(self):
        proj = Session.query(Project).first()
        matchdict = {'class_name': proj.klass.name, 'project_id': proj.id}
        json_data = {'name': 'Project 2', 'class_id': str(proj.klass.id)}
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = project_update(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Project name already exists for the class',
                         info['message'])

    def test_update_invalid_product_id(self):
        proj = Session.query(Project).first()
        matchdict = {'class_name': proj.klass.name, 'project_id': 100}
        json_data = {'name': 'Project 2', 'class_id': str(proj.klass.id)}
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid project_id', info['messages'])

    def test_update_inconsistent_class_id(self):
        proj = Session.query(Project).first()
        matchdict = {'class_name': proj.klass.name, 'project_id': proj.id}
        json_data = {'name': 'Project 2', 'class_id': str(100)}
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Inconsistent class specification', info['messages'])

    def test_update_inconsistent_class_name(self):
        proj = Session.query(Project).first()
        matchdict = {'class_name': 'Invalid name', 'project_id': proj.id}
        json_data = {'name': 'Project 2', 'class_id': str(proj.klass.id)}
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = project_update(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Inconsistent class specification', info['messages'])

    def test_update_no_change(self):
        proj = Session.query(Project).first()
        matchdict = {'class_name': proj.klass.name, 'project_id': proj.id}
        json_data = {'name': 'Project 1', 'class_id': str(proj.klass.id)}
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = project_update(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Nothing to change', info['message'])

    def test_update_valid(self):
        proj = Session.query(Project).first()
        matchdict = {'class_name': proj.klass.name, 'project_id': proj.id}
        json_data = {'name': 'Foobar', 'class_id': str(proj.klass.id)}
        request = self.make_request(json_body=json_data, matchdict=matchdict)
        info = project_update(request)
        proj = Session.merge(proj)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project updated', info['message'])
        self.assertEqual('Foobar', proj.name)

    def test_view(self):
        user = Session.query(User).filter_by(username='user1').first()
        proj = Session.query(Project).first()
        request = self.make_request(user=user,
                                    matchdict={'class_name': proj.klass.name,
                                               'project_id': proj.id})
        info = project_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project 1', info['project'].name)

    def test_view_incorrect_class_name(self):
        user = Session.query(User).filter_by(username='user1').first()
        proj = Session.query(Project).first()
        request = self.make_request(user=user,
                                    matchdict={'class_name': 'Test Invalid',
                                               'project_id': proj.id})
        info = project_view(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_user_not_part_of_class(self):
        user = User.fetch_by_name('user2')
        proj = Session.query(Project).first()
        request = self.make_request(user=user,
                                    matchdict={'class_name': proj.klass.name,
                                               'project_id': proj.id})
        info = project_view(request)
        self.assertIsInstance(info, HTTPForbidden)

    def test_view_invalid_id(self):
        user = Session.query(User).filter_by(username='user1').first()
        request = self.make_request(user=user,
                                    matchdict={'class_name': 'Test Invalid',
                                               'project_id': 100})
        info = project_view(request)
        self.assertIsInstance(info, HTTPNotFound)


class SessionTests(BaseAPITest):
    """Test the API methods involved in session creation and destruction."""

    def test_session_create_invalid(self):
        request = self.make_request(json_body={'username': 'user1',
                                               'password': 'badpw'})
        info = session_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Invalid login', info['message'])

    def test_session_create_no_params(self):
        request = self.make_request(json_body={})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(2, len(info['messages']))

    def test_session_create_no_password(self):
        request = self.make_request(json_body={'username': 'foo'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_session_create_no_username(self):
        request = self.make_request(json_body={'password': 'bar'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_session_create_valid(self):
        request = self.make_request(json_body={'username': 'user1',
                                               'password': 'pswd1'})
        info = session_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        self.assertEqual(route_path('user_item', request, username='user1'),
                         info['redir_location'])

    def test_session_edit(self):
        request = self.make_request()
        info = session_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Login', info['page_title'])


class SubmissionTests(BaseAPITest):
    """Test the API methods involved with Submissions."""
    @staticmethod
    def get_objects():
        user = Session.query(User).filter_by(username='user1').first()
        project = Session.query(Project).first()
        the_file = Session.query(File).first()
        json_data = {'file_ids': [str(the_file.id)], 'filenames': ['File 1'],
                     'project_id': str(project.id)}
        return user, json_data

    def test_create_invalid_file(self):
        user, json_data = self.get_objects()
        json_data['file_ids'][0] = '100'
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))
        self.assertTrue(info['messages'][0].startswith('Invalid file'))

    def test_create_invalid_project(self):
        user, json_data = self.get_objects()
        json_data['project_id'] = '100'
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))
        self.assertEqual('Invalid project_id', info['messages'][0])

    def test_create_list_mismatch(self):
        user, json_data = self.get_objects()
        json_data['file_ids'].append('1')
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(1, len(info['messages']))
        self.assertEqual('# file_ids must match # filenames',
                         info['messages'][0])

    def test_create_valid(self):
        user, json_data = self.get_objects()
        request = self.make_request(user=user, json_body=json_data)
        info = submission_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected_prefix = route_path('submission', request,
                                     submission_id=0)[:-1]
        self.assertTrue(info['redir_location'].startswith(expected_prefix))


class UserTests(BaseAPITest):
    """The the API methods involved with modifying user information."""

    def test_user_create_duplicate_name(self):
        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'password': 'Foobar', 'username': 'user1'}
        request = self.make_request(json_body=json_data)
        info = user_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Username \'user1\' already exists', info['message'])

    def test_user_create_invalid_email(self):
        json_data = {'name': 'Foobar', 'password': 'Foobar',
                     'username': 'foobar'}
        for item in ['', 'a' * 5]:
            json_data['email'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_name(self):
        json_data = {'email': 'foo@bar.com', 'password': 'Foobar',
                     'username': 'foobar'}
        for item in ['', 'a' * 2]:
            json_data['name'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_password(self):
        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'username': 'foobar'}
        for item in ['', 'a' * 5]:
            json_data['password'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_username(self):
        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'password': 'foobar'}
        for item in ['', 'a' * 2, 'a' * 17]:
            json_data['username'] = item
            request = self.make_request(json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_no_params(self):
        request = self.make_request(json_body={})
        info = user_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(4, len(info['messages']))

    def test_user_create_valid(self):
        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'password': 'Foobar', 'username': 'user3'}
        request = self.make_request(json_body=json_data)
        info = user_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected = route_path('session', request, _query={'username': 'user3'})
        self.assertEqual(expected, info['redir_location'])
        username = json_data['username']
        user = Session.query(User).filter_by(username=username).first()
        self.assertEqual(json_data['email'], user.email)
        self.assertEqual(json_data['name'], user.name)
        self.assertNotEqual(json_data['password'], user._password)

    def test_user_edit(self):
        request = self.make_request()
        info = user_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create User', info['page_title'])

    def test_user_list(self):
        request = self.make_request()
        info = user_list(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual(2, len(info['users']))
        self.assertEqual('user1', info['users'][0].username)

    def test_user_view(self):
        request = self.make_request(matchdict={'username': 'user1'})
        info = user_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('user1', info['user'].username)

    def test_user_view_invalid(self):
        request = self.make_request(matchdict={'username': 'Invalid'})
        info = user_view(request)
        self.assertIsInstance(info, HTTPNotFound)


### Non-view tests
class DummyTemplateTest(unittest.TestCase):
    def test_default_attribute_values(self):
        a = DummyTemplateAttr()
        self.assertEqual(None, a.bar)
        self.assertEqual(None, a.foo)

    def test_explicit_default_attribute_values(self):
        a = DummyTemplateAttr('a')
        self.assertEqual('a', a.bar)
        self.assertEqual('a', a.foo)

    def test_set_attribute(self):
        a = DummyTemplateAttr()
        a.foo = 'foo'
        self.assertEqual(None, a.bar)
        self.assertEqual('foo', a.foo)


if __name__ == '__main__':
    unittest.main()
