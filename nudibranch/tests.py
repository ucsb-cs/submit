import unittest
from pyramid import testing
import transaction


def _init_testing_db():
    """Create an in-memory database for testing."""
    from sqlalchemy import create_engine
    from .models import Class, Session, User, initialize_sql
    engine = create_engine('sqlite://')
    initialize_sql(engine)

    items = [Class(name='Test 101'),
             User(email='', name='User', username='user1', password='pswd1')]
    Session.add_all(items)


class BaseAPITest(unittest.TestCase):
    """Base test class for all API method (or controller) tests."""
    ROUTES = {'class': '/test_class',
              'class_new_form': '/test_class/edit',
              'class_item': '/test_class/{class_name}',
              'class_edit_form': '/test_class/{class_name}/edit',
              'home': '/test_home',
              'session': '/test_session',
              'user': '/test_user',
              'user_new_form': '/test_user/edit',
              'user_item': '/test_user/{username}',
              'user_edit_form': '/test_user/{username}/edit'}

    def make_request(self, path, **kwargs):
        """Build the request object used in view tests."""
        kwargs.setdefault('path', BaseAPITest.ROUTES[path])
        kwargs.setdefault('user', None)
        request = testing.DummyRequest(**kwargs)
        return request

    def setUp(self):
        """Initialize the database and add routes."""
        self.config = testing.setUp()
        _init_testing_db()
        for key, value in BaseAPITest.ROUTES.items():
            self.config.add_route(key, value)

    def tearDown(self):
        """Destroy the session and end the pyramid testing."""
        from .models import Session
        testing.tearDown()
        transaction.abort()
        Session.remove()


class BasicTests(BaseAPITest):
    def test_site_layout_decorator(self):
        from .views import home
        from chameleon.zpt.template import Macro
        request = self.make_request('home')
        info = home(request)
        self.assertIsInstance(info['_LAYOUT'], Macro)
        self.assertRaises(ValueError, info['_S'], 'favicon.ico')

    def test_home(self):
        from .views import home
        request = self.make_request('home')
        info = home(request)
        self.assertEqual('Home', info['page_title'])


class ClassTests(BaseAPITest):
    """The the API methods involved with modifying class information."""

    def test_class_create_duplicate_name(self):
        from .views import class_create
        from pyramid.httpexceptions import HTTPConflict
        json_data = {'name': 'Test 101'}
        request = self.make_request('class', json_body=json_data)
        info = class_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Class \'Test 101\' already exists', info['message'])

    def test_class_create_invalid_name(self):
        from .views import class_create
        from pyramid.httpexceptions import HTTPBadRequest

        json_data = {}
        for item in ['', 'a' * 2]:
            json_data['name'] = item
            request = self.make_request('class', json_body=json_data)
            info = class_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_class_create_no_params(self):
        from .views import class_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('class', json_body={})
        info = class_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_class_create_valid(self):
        from .models import Session, Class
        from .views import class_create
        from pyramid.httpexceptions import HTTPCreated
        json_data = {'name': 'Foobar'}
        request = self.make_request('user', json_body=json_data)
        info = class_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        self.assertEqual(self.ROUTES['class'], info['redir_location'])
        name = json_data['name']
        klass = Session.query(Class).filter_by(name=name).first()
        self.assertEqual(json_data['name'], klass.name)

    def test_class_edit(self):
        from .views import class_edit
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('class_edit_form')
        info = class_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create Class', info['page_title'])

    def test_class_list(self):
        from .views import class_list
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('class')
        info = class_list(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual(1, len(info['classes']))
        self.assertEqual('Test 101', info['classes'][0].name)

    def test_class_view(self):
        from .views import class_view
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('class_item',
                                    matchdict={'class_name': 'Test 101'})
        info = class_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Test 101', info['klass'].name)


class SessionTests(BaseAPITest):
    """Test the API methods involved in session creation and destruction."""

    def test_session_create_invalid(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPConflict
        request = self.make_request('session', json_body={'username': 'user1',
                                                          'password': 'badpw'})
        info = session_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Invalid login', info['message'])

    def test_session_create_no_params(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('session', json_body={})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(2, len(info['messages']))

    def test_session_create_no_password(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('session', json_body={'username': 'foo'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_session_create_no_username(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('session', json_body={'password': 'bar'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(1, len(info['messages']))

    def test_session_create_valid(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPCreated
        request = self.make_request('session', json_body={'username': 'user1',
                                                          'password': 'pswd1'})
        info = session_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected_url = self.ROUTES['user_item'].format(username='user1')
        self.assertEqual(expected_url, info['redir_location'])

    def test_session_edit(self):
        from .views import session_edit
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('session')
        info = session_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Login', info['page_title'])


class UserTests(BaseAPITest):
    """The the API methods involved with modifying user information."""

    def test_user_create_duplicate_name(self):
        from .views import user_create
        from pyramid.httpexceptions import HTTPConflict

        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'password': 'Foobar', 'username': 'user1'}
        request = self.make_request('user', json_body=json_data)
        info = user_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual('Username \'user1\' already exists', info['message'])

    def test_user_create_invalid_email(self):
        from .views import user_create
        from pyramid.httpexceptions import HTTPBadRequest

        json_data = {'name': 'Foobar', 'password': 'Foobar',
                     'username': 'foobar'}
        for item in ['', 'a' * 5]:
            json_data['email'] = item
            request = self.make_request('user', json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_name(self):
        from .views import user_create
        from pyramid.httpexceptions import HTTPBadRequest

        json_data = {'email': 'foo@bar.com', 'password': 'Foobar',
                     'username': 'foobar'}
        for item in ['', 'a' * 2]:
            json_data['name'] = item
            request = self.make_request('user', json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_password(self):
        from .views import user_create
        from pyramid.httpexceptions import HTTPBadRequest

        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'username': 'foobar'}
        for item in ['', 'a' * 5]:
            json_data['password'] = item
            request = self.make_request('user', json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_invalid_username(self):
        from .views import user_create
        from pyramid.httpexceptions import HTTPBadRequest

        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'password': 'foobar'}
        for item in ['', 'a' * 2, 'a' * 17]:
            json_data['username'] = item
            request = self.make_request('user', json_body=json_data)
            info = user_create(request)
            self.assertEqual(HTTPBadRequest.code, request.response.status_code)
            self.assertEqual('Invalid request', info['error'])
            self.assertEqual(1, len(info['messages']))

    def test_user_create_no_params(self):
        from .views import user_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('user', json_body={})
        info = user_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual('Invalid request', info['error'])
        self.assertEqual(4, len(info['messages']))

    def test_user_create_valid(self):
        from .models import Session, User
        from .views import user_create
        from pyramid.httpexceptions import HTTPCreated
        json_data = {'email': 'foo@bar.com', 'name': 'Foobar',
                     'password': 'Foobar', 'username': 'user2'}
        request = self.make_request('user', json_body=json_data)
        info = user_create(request)
        self.assertEqual(HTTPCreated.code, request.response.status_code)
        expected_url = '{0}?username={1}'.format(self.ROUTES['session'],
                                                 'user2')
        self.assertEqual(expected_url, info['redir_location'])
        username = json_data['username']
        user = Session.query(User).filter_by(username=username).first()
        self.assertEqual(json_data['email'], user.email)
        self.assertEqual(json_data['name'], user.name)
        self.assertNotEqual(json_data['password'], user._password)

    def test_user_edit(self):
        from .views import user_edit
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('user_edit_form')
        info = user_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('Create User', info['page_title'])

    def test_user_list(self):
        from .views import user_list
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('user')
        info = user_list(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual(1, len(info['users']))
        self.assertEqual('user1', info['users'][0].username)

    def test_user_view(self):
        from .views import user_view
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('user_item',
                                    matchdict={'username': 'user1'})
        info = user_view(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual('user1', info['user'].username)
