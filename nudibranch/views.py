from pyramid.response import Response
from pyramid.view import notfound_view_config, view_config
from .helpers import site_layout


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Nout Found')


@view_config(route_name='home', renderer='templates/home.pt')
@site_layout
def home(request):
    return {'page_title': 'Home'}
