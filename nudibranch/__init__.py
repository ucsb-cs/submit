from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.security import ALL_PERMISSIONS, Allow, Authenticated
from sqlalchemy import engine_from_config
from .models import initialize_sql
from .security import get_user, group_finder


class Root(object):
    __acl__ = [(Allow, Authenticated, 'authenticated'),
               (Allow, 'admin', ALL_PERMISSIONS)]

    def __init__(self, request):
        self.request = request


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    # Initialize the database
    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine, populate=True)

    # Configure the webapp
    authen = AuthTktAuthenticationPolicy(secret='<PYRAMID_SECRET>',
                                         callback=group_finder)
    author = ACLAuthorizationPolicy()
    config = Configurator(settings=settings, authentication_policy=authen,
                          authorization_policy=author, root_factory=Root)
    config.add_static_view('static', 'static', cache_max_age=3600)
    # Add user attribute to request
    config.set_request_property(get_user, 'user', reify=True)

    # Application routes
    config.add_route('home', '/')
    config.add_route('class', '/class')
    config.add_route('class_new_form', '/class/edit')
    config.add_route('class_item', '/class/{class_name}')
    config.add_route('class_join', '/class/{class_name}/{username}')
    config.add_route('class_edit_form', '/class/{class_name}/edit')
    config.add_route('session', '/session')
    config.add_route('user', '/user')
    config.add_route('user_new_form', '/user/edit')
    config.add_route('user_item', '/user/{username}')
    config.add_route('user_edit_form', '/user/{username}/edit')
    config.scan()
    return config.make_wsgi_app()
