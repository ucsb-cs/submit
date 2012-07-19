from pyramid.config import Configurator
from sqlalchemy import engine_from_config
from .models import initialize_sql


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """

    # Initialize the database
    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)

    # Configure the webapp
    config = Configurator(settings=settings)
    config.add_static_view('static', 'static', cache_max_age=3600)

    # Application routes
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('userhome', '/userhome/{username}')
    config.add_route('create', '/create/User')
    config.scan()
    return config.make_wsgi_app()
