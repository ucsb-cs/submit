from pyramid.response import Response
from pyramid.view import notfound_view_config, view_config
from .helpers import site_layout, url_path, route_path
from urllib.parse import urljoin
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from .models import Session, User


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


@view_config(route_name='home', renderer='templates/home.pt')
@site_layout
def home(request):
    return {'page_title': 'Home',
            'login_link': route_path(request, 'login'),
            'user_link': route_path(request, 'create')}


@view_config(route_name='login', renderer='templates/login.pt')
@site_layout
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
    return {'page_title': 'Login', 'action_path': route_path(request, 'login'),
            'failed': failed, 'user': user}


@view_config(route_name='userhome', renderer='templates/userhome.pt')
@site_layout
def userhome(request):
    return {'page_title': 'User Home',
            'username': request.matchdict['username']}


@view_config(route_name='create', renderer='templates/create_user.pt')
@site_layout
def create(request):
    failed = False
    username = ''
    if 'submit' in request.POST:
        user = request.POST.get('Username', '').strip()
        name = request.POST.get('Name', '').strip()
        password = request.POST.get('Password', '').strip()
        email = request.POST.get('Email', '').strip()
        if (user == '') or (password == '') or (email == '') or (name == ''):
            failed = True
        else:
            failed = False
            new_user = User(name=name,
                            email=email,
                            username=user,
                            password=password)
            Session.add(new_user)
            return HTTPFound(location=route_path(request,
                                                 'userhome',
                                                 username=user))

    return {'page_title': 'Create User',
            'action_path': route_path(request, 'create'),
            'failed': failed}
