from pyramid.response import Response
from pyramid.view import notfound_view_config, view_config
from .helpers import site_layout, url_path, route_path
from urllib.parse import urljoin


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Nout Found')


@view_config(route_name='home', renderer='templates/home.pt')
@site_layout
def home(request):
    return {'page_title': 'Home'}


@view_config(route_name='login', renderer='templates/login.pt')
@site_layout
def login(request):
    return dict(
        page_title='Login',
        action_path=request.application_url + '/login',
    )
