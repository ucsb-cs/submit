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


def add_routes(config):
    # Application routes
    config.add_route('home', '/')
    config.add_route('class', '/class')
    config.add_route('class_item', '/class/{class_name}')
    config.add_route('file', '/file')
    config.add_route('file_item', '/file/{sha1sum}')
    config.add_route('file_item_info', '/file/{sha1sum}/info')
    config.add_route('file_verifier', '/file_verifier')
    config.add_route('file_verifier_item', '/file_verifier/{file_verifier_id}')
    config.add_route('project', '/project')
    config.add_route('project_item_summary',
                     '/class/{class_name}/{project_id}')
    config.add_route('project_item_detailed',
                     '/class/{class_name}/{project_id}/{user_id}')
    config.add_route('session', '/session')
    config.add_route('submission', '/submission')
    config.add_route('submission_item', '/submission/{submission_id}')
    config.add_route('test_case', '/test_case')
    config.add_route('test_case_item', '/test_case/{test_case_id}')
    config.add_route('user', '/user')
    config.add_route('user_class_join', '/user/{username}/{class_name}')
    config.add_route('user_item', '/user/{username}')

    # Form view routes
    config.add_route('class_new', '/form/class')
    config.add_route('class_edit', '/form/class/{class_name}')
    config.add_route('project_new', '/form/class/{class_name}/project')
    config.add_route('project_edit', '/form/project/{project_id}')
    config.add_route('user_new', '/form/user')
    config.add_route('user_edit', '/form/user/{username}')


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

    add_routes(config)
    config.scan()
    return config.make_wsgi_app()
