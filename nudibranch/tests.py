import unittest
from pyramid import testing
import transaction


def _init_testing_db():
    """Create an in-memory database for testing."""
    from sqlalchemy import create_engine
    from .models import initialize_sql
    engine = create_engine('sqlite://')
    initialize_sql(engine)


class BaseAPITest(unittest.TestCase):
    """Base test class for all API method (or controller) tests."""
    ROUTES = {'session': '/test_session'}

    def make_request(self, path, **kwargs):
        """Build the request object used in view tests."""
        kwargs.setdefault('path', BaseAPITest.ROUTES[path])
        kwargs.setdefault('json_body', {})
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
        Session.remove()


class SessionTests(BaseAPITest):
    """Test the API methods involved in session creation and destruction."""

    def test_session_create_invalid_login(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPConflict
        request = self.make_request('session', json_body={'username': 'foo',
                                                          'password': 'bar'})
        info = session_create(request)
        self.assertEqual(HTTPConflict.code, request.response.status_code)
        self.assertEqual(info['message'], 'Invalid login')

    def test_session_create_with_no_params(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('session', json_body={})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(info['error'], 'Invalid request')
        self.assertEqual(len(info['messages']), 2)

    def test_session_create_with_no_password(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('session', json_body={'username': 'foo'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(info['error'], 'Invalid request')
        self.assertEqual(len(info['messages']), 1)

    def test_session_create_with_no_username(self):
        from .views import session_create
        from pyramid.httpexceptions import HTTPBadRequest
        request = self.make_request('session', json_body={'password': 'bar'})
        info = session_create(request)
        self.assertEqual(HTTPBadRequest.code, request.response.status_code)
        self.assertEqual(info['error'], 'Invalid request')
        self.assertEqual(len(info['messages']), 1)

    def test_session_edit(self):
        from .views import session_edit
        from pyramid.httpexceptions import HTTPOk
        request = self.make_request('session')
        info = session_edit(request)
        self.assertEqual(HTTPOk.code, request.response.status_code)
        self.assertEqual(info['page_title'], 'Login')


"""
class ViewTests(unittest.TestCase):
    def test_site_layout_decorator(self):
        from .views import home
        from chameleon.zpt.template import Macro
        request = self._make_request()
        info = home(request)
        self.assertIsInstance(info['_LAYOUT'], Macro)
        self.assertRaises(ValueError, info['_S'], 'favicon.ico')

    def test_home(self):
        from .views import home
        request = self._make_request()
        info = home(request)
        self.assertEqual('Home', info['page_title'])

    def test_create_user_get(self):
        from .views import user_create
        request = self._make_request()
        info = user_create(request)
        self.assertEqual(self.TEST_PATHS['user_create'], info['action_path'])
        self.assertEqual(False, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_user_create_post_only_submission_param(self):
        from .views import user_create
        post_params = {'submit': 'submit'}
        request = self._make_request(POST=post_params)
        info = user_create(request)
        self.assertEqual(self.TEST_PATHS['user_create'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_user_create_post_successful(self):
        from .views import user_create
        post_params = {'submit': 'submit',
                       'Password': 'password',
                       'Username': 'foobar',
                       'Name': 'foo',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = user_create(request)
        # Verify the user is redirected to their userhome page.
        self.assertEqual(self.TEST_PATHS['userhome'].format(username='foobar'),
                         info.location)

    def test_user_create_post_no_password(self):
        from .views import user_create
        post_params = {'submit': 'submit',
                       'Username': 'foobar',
                       'Name': 'foo',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = user_create(request)
        self.assertEqual(self.TEST_PATHS['user_create'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_user_create_post_no_username(self):
        from .views import user_create
        post_params = {'submit': 'submit',
                       'Password': 'password',
                       'Name': 'foo',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = user_create(request)
        self.assertEqual(self.TEST_PATHS['user_create'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_user_create_post_no_name(self):
        from .views import user_create
        post_params = {'submit': 'submit',
                       'Username': 'foobar',
                       'Password': 'password',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = user_create(request)
        self.assertEqual(self.TEST_PATHS['user_create'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_user_create_post_no_email(self):
        from .views import user_create
        post_params = {'submit': 'submit',
                       'Username': 'foobar',
                       'Name': 'foo',
                       'Password': 'password'}
        request = self._make_request(POST=post_params)
        info = user_create(request)
        self.assertEqual(self.TEST_PATHS['user_create'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_create_class_get(self):
        from .views import create_class
        request = self._make_request()
        info = create_class(request)
        self.assertEqual(self.TEST_PATHS['create_class'], info['action_path'])
        self.assertEqual(False, info['failed'])
        self.assertEqual('Create Class', info['page_title'])

    def test_create_class_post_only_submission_param(self):
        from .views import create_class
        post_params = {'submit': 'submit'}
        request = self._make_request(POST=post_params)
        info = create_class(request)
        self.assertEqual(self.TEST_PATHS['create_class'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create Class', info['page_title'])

    def test_create_class_post_successful(self):
        from .views import create_class
        post_params = {'submit': 'submit',
                       'Class_Name': 'foobar'}
        request = self._make_request(POST=post_params)
        info = create_class(request)
        self.assertEqual(self.TEST_PATHS['create_class'], info['action_path'])
        self.assertEqual(False, info['failed'])
        self.assertEqual(["Class added!"], info['message'])
"""
