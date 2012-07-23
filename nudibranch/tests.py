import unittest
from pyramid import testing


def _init_testing_db():
    from .models import Session
    from .models import Base


class ViewTests(unittest.TestCase):
    # Need to add a "testing" version of all routes here
    TEST_PATHS = {'home': '/test_home',
                  'login': '/test_login',
                  'userhome': '/test_userhome/{username}',
                  'create_user': '/test_create/User'}

    def setUp(self):
        self.config = testing.setUp()
        for key, value in self.TEST_PATHS.items():
            self.config.add_route(key, value)

    def tearDown(self):
        testing.tearDown()

    def _make_request(self, **kwargs):
        request = testing.DummyRequest(**kwargs)
        request.app_url = None
        return request

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

    def test_login_get(self):
        from .views import login
        request = self._make_request()
        info = login(request)
        self.assertEqual(self.TEST_PATHS['login'], info['action_path'])
        self.assertEqual(False, info['failed'])
        self.assertEqual('Login', info['page_title'])
        self.assertEqual('', info['user'])

    def test_login_post_only_submission_param(self):
        from .views import login
        post_params = {'submit': 'submit'}
        request = self._make_request(POST=post_params)
        info = login(request)
        self.assertEqual(self.TEST_PATHS['login'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Login', info['page_title'])
        self.assertEqual('', info['user'])

    def test_login_post_no_password(self):
        from .views import login
        post_params = {'submit': 'submit', 'Username': 'foobar'}
        request = self._make_request(POST=post_params)
        info = login(request)
        self.assertEqual(self.TEST_PATHS['login'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Login', info['page_title'])
        self.assertEqual('foobar', info['user'])

    def test_login_post_no_username(self):
        from .views import login
        post_params = {'submit': 'submit', 'Password': 'password'}
        request = self._make_request(POST=post_params)
        info = login(request)
        self.assertEqual(self.TEST_PATHS['login'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Login', info['page_title'])
        self.assertEqual('', info['user'])

    def test_login_post_successful(self):
        from .views import login
        post_params = {'submit': 'submit',
                       'Password': 'password',
                       'Username': 'foobar'}
        request = self._make_request(POST=post_params)
        info = login(request)
        # Verify the user is redirected to their userhome page.
        self.assertEqual(self.TEST_PATHS['userhome'].format(username='foobar'),
                         info.location)

    def test_create_user_get(self):
        from .views import create_user
        request = self._make_request()
        info = create_user(request)
        self.assertEqual(self.TEST_PATHS['create_user'], info['action_path'])
        self.assertEqual(False, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_create_user_post_only_submission_param(self):
        from .views import create_user
        post_params = {'submit': 'submit'}
        request = self._make_request(POST=post_params)
        info = create_user(request)
        self.assertEqual(self.TEST_PATHS['create_user'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_create_user_post_successful(self):
        from .views import create_user
        post_params = {'submit': 'submit',
                       'Password': 'password',
                       'Username': 'foobar',
                       'Name': 'foo',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = create_user(request)
        # Verify the user is redirected to their userhome page.
        self.assertEqual(self.TEST_PATHS['userhome'].format(username='foobar'),
                         info.location)

    def test_create_user_post_no_password(self):
        from .views import create_user
        post_params = {'submit': 'submit',
                       'Username': 'foobar',
                       'Name': 'foo',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = create_user(request)
        self.assertEqual(self.TEST_PATHS['create_user'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_create_user_post_no_username(self):
        from .views import create_user
        post_params = {'submit': 'submit',
                       'Password': 'password',
                       'Name': 'foo',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = create_user(request)
        self.assertEqual(self.TEST_PATHS['create_user'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_create_user_post_no_name(self):
        from .views import create_user
        post_params = {'submit': 'submit',
                       'Username': 'foobar',
                       'Password': 'password',
                       'Email': 'foobar@email.com'}
        request = self._make_request(POST=post_params)
        info = create_user(request)
        self.assertEqual(self.TEST_PATHS['create_user'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])

    def test_create_user_post_no_email(self):
        from .views import create_user
        post_params = {'submit': 'submit',
                       'Username': 'foobar',
                       'Name': 'foo',
                       'Password': 'password'}
        request = self._make_request(POST=post_params)
        info = create_user(request)
        self.assertEqual(self.TEST_PATHS['create_user'], info['action_path'])
        self.assertEqual(True, info['failed'])
        self.assertEqual('Create User', info['page_title'])
