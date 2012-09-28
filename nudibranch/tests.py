import transaction
import unittest
from chameleon.zpt.template import Macro
from nudibranch import add_routes
from nudibranch.models import *
from nudibranch.views import *
from pyramid import testing
from pyramid.httpexceptions import (HTTPBadRequest, HTTPConflict, HTTPCreated,
                                    HTTPNotFound, HTTPOk)
from pyramid.url import route_path
from sqlalchemy import create_engine


def _init_testing_db():
    """Create an in-memory database for testing."""
    engine = create_engine('sqlite://')
    initialize_sql(engine)

    klass = Class(name='Test 101')
    items = [klass,
             User(email='', name='User', username='user1', password='pswd1')]
    Session.add_all(items)
    Session.flush()
    project = Project(name='Project 1', class_id=klass.id)
    Session.add_all([project, Project(name='Project 2', class_id=klass.id)])
    Session.flush()
    Session.add(FileVerifier(filename='File 1', min_size=0, min_lines=0,
                             project_id=project.id))


class BaseAPITest(unittest.TestCase):
    """Base test class for all API method (or controller) tests."""

    def make_request(self, **kwargs):
        """Build the request object used in view tests."""
        kwargs.setdefault('user', None)
        request = testing.DummyRequest(**kwargs)
        return request

    def setUp(self):
        """Initialize the database and add routes."""
        self.config = testing.setUp()
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
        self.assertEqual(project.klass.id, info['class_id'])

    def test_new(self):
        klass = Session.query(Class).first()
        request = self.make_request(matchdict={'class_name': klass.name})
        info = project_new(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create Project', info['page_title'])
        self.assertEqual(klass.id, info['class_id'])

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
        proj = Session.query(Project).first()
        request = self.make_request(matchdict={'class_name': proj.klass.name,
                                               'project_id': proj.id})
        info = project_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Project 1', info['project'].name)

    def test_view_incorrect_class_name(self):
        proj = Session.query(Project).first()
        request = self.make_request(matchdict={'class_name': 'Test Invalid',
                                               'project_id': proj.id})
        info = project_view(request)
        self.assertIsInstance(info, HTTPNotFound)

    def test_view_invalid_id(self):
        request = self.make_request(matchdict={'class_name': 'Test Invalid',
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
                     'password': 'Foobar', 'username': 'user2'}
        request = self.make_request(json_body=json_data)
        info = user_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected = route_path('session', request, _query={'username': 'user2'})
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
        self.assertEqual(1, len(info['users']))
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


if __name__ == '__main__':
    unittest.main()
