import transaction
from sqlalchemy.exc import IntegrityError
from pyramid_addons.helpers import (http_bad_request, http_conflict,
                                    http_created, http_gone, http_ok,
                                    site_layout)
from pyramid_addons.validation import String, WhiteSpaceString, validated_form
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.response import Response
from pyramid.security import (Authenticated, forget, remember)
from pyramid.view import notfound_view_config, view_config
from urllib.parse import urljoin
from .models import Class, Session, User


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


@view_config(route_name='class', request_method='PUT',
             permission='admin', renderer='json')
@validated_form(name=String('name', invalid_re='^edit$', min_length=3))
def class_create(request, name):
    session = Session()
    klass = Class(name=name)
    session.add(klass)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request,
                             'Class {0!r} already exists'.format(name))
    return http_created(request, redir_location=request.route_path('class'))


@view_config(route_name='class_new', renderer='templates/class_create.pt',
             request_method='GET', permission='admin')
@site_layout('nudibranch:templates/layout.pt')
def class_edit(request):
    return {'page_title': 'Create Class'}


@view_config(route_name='class', request_method='GET',
             permission='authenticated', renderer='templates/class_list.pt')
@site_layout('nudibranch:templates/layout.pt')
def class_list(request):
    session = Session()
    classes = session.query(Class).all()
    return {'page_title': 'Login', 'classes': classes}


@view_config(route_name='class_item', request_method='GET',
             renderer='templates/class_view.pt', permission='authenticated')
@site_layout('nudibranch:templates/layout.pt')
def class_view(request):
    session = Session()
    klass = Class.fetch_by_name(request.matchdict['class_name'])
    if not klass:
        return HTTPNotFound()
    return {'page_title': 'Class Page', 'klass': klass}


@view_config(route_name='home', renderer='templates/home.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def home(request):
    if request.user:
        url = request.route_path('user_item', username=request.user.username)
        return HTTPFound(location=url)
    return {'page_title': 'Home'}


@view_config(route_name='project_new', renderer='templates/project_create.pt',
             request_method='GET', permission='admin')
@site_layout('nudibranch:templates/layout.pt')
def project_edit(request):
    session = Session()
    klass = Class.fetch_by_name(request.matchdict['class_name'])
    if not klass:
        return HTTPNotFound()
    return {'page_title': 'Create Project', 'class_id': klass.id}


@view_config(route_name='session', renderer='json', request_method='PUT')
@validated_form(username=String('username'),
                password=WhiteSpaceString('password'))
def session_create(request, username, password):
    user = User.login(username, password)
    if user:
        headers = remember(request, user.id)
        url = request.route_path('user_item', username=user.username)
        retval = http_created(request, redir_location=url, headers=headers)
    else:
        retval = http_conflict(request, 'Invalid login')
    return retval


@view_config(route_name='session', renderer='json', request_method='DELETE',
             permission='authenticated')
@validated_form()
def session_destroy(request):
    headers = forget(request)
    return http_gone(request, redir_location=request.route_path('home'),
                     headers=headers)


@view_config(route_name='session', renderer='templates/login.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def session_edit(request):
    username = request.GET.get('username', '')
    return {'page_title': 'Login', 'username': username}


@view_config(route_name='user_class_join', request_method='POST',
             permission='authenticated', renderer='json')
@validated_form()
def user_class_join(request):
    class_name = request.matchdict['class_name']
    username = request.matchdict['username']
    if request.user.username != username:
        return http_bad_request(request, 'Invalid user')
    session = Session()
    klass = Session.query(Class).filter_by(name=class_name).first()
    if not klass:
        return http_bad_request(request, 'Invalid class')
    request.user.classes.append(klass)
    session.add(request.user)
    transaction.commit()
    return http_ok(request, 'Class joined')


@view_config(route_name='user', renderer='json', request_method='PUT')
@validated_form(name=String('name', min_length=3),
                username=String('username', invalid_re='^edit$',
                                min_length=3, max_length=16),
                password=WhiteSpaceString('password', min_length=6),
                email=String('email', min_length=6))
def user_create(request, name, username, password, email):
    session = Session()
    user = User(name=name, username=username, password=password,
                email=email, is_admin=False)
    session.add(user)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request,
                             'Username {0!r} already exists'.format(username))
    redir_location = request.route_path('session',
                                        _query={'username': username})
    return http_created(request, redir_location=redir_location)


@view_config(route_name='user_new', renderer='templates/user_create.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def user_edit(request):
    return {'page_title': 'Create User'}


@view_config(route_name='user', request_method='GET', permission='admin',
             renderer='templates/user_list.pt')
@site_layout('nudibranch:templates/layout.pt')
def user_list(request):
    session = Session()
    users = session.query(User).all()
    return {'page_title': 'User List', 'users': users}


@view_config(route_name='user_item', request_method='GET',
             renderer='templates/user_view.pt', permission='authenticated')
@site_layout('nudibranch:templates/layout.pt')
def user_view(request):
    session = Session()
    user = User.fetch_by_name(request.matchdict['username'])
    if not user:
        return HTTPNotFound()
    return {'page_title': 'User Page', 'user': user}
