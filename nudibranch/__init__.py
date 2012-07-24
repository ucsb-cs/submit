from pyramid.config import Configurator
from sqlalchemy import engine_from_config
from .models import initialize_sql
from pyramid.security import ALL_PERMISSIONS, Allow, Authenticated
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from .security import group_finder


class Root(object):
    __acl__ = [(Allow, Authenticated, 'student'),
               (Allow, 'admin', ALL_PERMISSIONS)]

    def __init__(self, request):
        self.request = request


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    # Initialize the database
    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)
    # Configure the webapp
    authen = AuthTktAuthenticationPolicy(secret='<PYRAMID_SECRET>',
                                         callback=group_finder)
    author = ACLAuthorizationPolicy()
    config = Configurator(settings=settings,
                          authentication_policy=authen,
                          authorization_policy=author,
                          root_factory=Root)
    config.add_static_view('static', 'static', cache_max_age=3600)

    # Application routes
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('userhome', '/userhome/{username}')
    config.add_route('create_user', '/create/User')
    config.add_route('create_class', '/create/Class')
    config.scan()
    return config.make_wsgi_app()
