from pyramid.response import Response
from pyramid.view import notfound_view_config, view_config
from .helpers import site_layout, url_path, route_path, use_site_layout
from urllib.parse import urljoin
from pyramid.httpexceptions import HTTPFound, HTTPNotFound


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


@view_config(route_name='home', renderer='templates/home.pt')
@site_layout
def home(request):
    return {'page_title': 'Home', 'link': route_path(request, 'login')}


@view_config(route_name='login', renderer='templates/login.pt')
def login(request):
    failed = False
    user = ''
    if 'submit' in request.POST:
        user = request.POST.get('Username', '').strip()
        password = request.POST.get('Password', '').strip()
        if user == '':
            failed = True
        elif password == '':
            failed = True
        else:
            failed = False
            return HTTPFound(location=route_path(request, 'userhome',
                                                 username=user))
    return use_site_layout(request,
                           page_title='Login',
                           action_path=route_path(request, 'login'),
                           failed=failed,
                           user=user)


@view_config(route_name='userhome', renderer='templates/userhome.pt')
@site_layout
def userhome(request):
    return {'page_title': 'User Home',
            'username': request.matchdict['username']}
