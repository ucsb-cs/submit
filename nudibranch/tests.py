import unittest
from pyramid import testing


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_site_layout_decorator(self):
        from .views import home
        from chameleon.zpt.template import Macro
        request = testing.DummyRequest()
        info = home(request)
        self.assertIsInstance(info['_LAYOUT'], Macro)

    def test_home(self):
        from .views import home
        request = testing.DummyRequest()
        info = home(request)
        self.assertEqual(info['page_title'], 'Home')
