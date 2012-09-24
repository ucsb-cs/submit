import transaction
from sqlalchemy.exc import IntegrityError
from pyramid_addons.helpers import (http_conflict, http_created, http_gone,
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


@view_config(route_name='home', renderer='templates/home.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def home(request):
    if request.user:
        url = request.route_path('user_view', username=request.user.username)
        return HTTPFound(location=url)
    return {'page_title': 'Home'}


@view_config(route_name='class_create', request_method='PUT',
             permission='admin', renderer='json')
@validated_form(name=String('name', min_length=3))
def class_create(request, name):
    session = Session()
    klass = Class(name=name)
    session.add(klass)
    try:
        transaction.commit()
    except IntegrityError:
        return http_conflict(request,
                             'Class {0!r} already exists'.format(name))
    return http_created(request, redir_location=request.route_path('class'))


@view_config(route_name='class_create', renderer='templates/class_create.pt',
             request_method='GET', permission='admin')
@site_layout('nudibranch:templates/layout.pt')
def class_edit(request):
    return {'page_title': 'Create Class'}


@view_config(route_name='class_list', request_method='GET', permission='admin',
             renderer='templates/class_list.pt')
@site_layout('nudibranch:templates/layout.pt')
def class_list(request):
    session = Session()
    classes = session.query(Class).all()
    return {'page_title': 'Login', 'classes': classes}



"""
    failed = False
    message = []
    for course in session.query(Class):
        message.append(course.class_name)

    if 'remove_submit' in request.POST:
        course_name = request.POST.get('Class_Name', '').strip()
        if course_name == '':
            failed = True
        else:
            to_remove = Class.fetch_by_name(course_name)
            if to_remove:
                session.delete(to_remove)
                transaction.commit()
                message.remove(to_remove.class_name)
            else:
                failed = True

    if 'rename_submit' in request.POST:
        old_name = request.POST.get('Old_Name', '').strip()
        new_name = request.POST.get('New_Name', '').strip()
        if (old_name == '') or (new_name == ''):
            failed = True
        else:
            rename = Class.fetch_by_name(old_name)
            if rename:
                rename.class_name = new_name
                message.remove(old_name)
                message.append(new_name)
                transaction.commit()
            else:
                failed = True

    return {'page_title': 'Edit Class',
            'action_path': request.route_path('edit_class'),
            'failed': failed,
            'message': message}
"""


@view_config(route_name='session', renderer='json', request_method='PUT')
@validated_form(username=String('username'),
                password=WhiteSpaceString('password'))
def session_create(request, username, password):
    user = User.login(username, password)
    if user:
        headers = remember(request, user.id)
        url = request.route_path('user_view', username=user.username)
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


@view_config(route_name='user_create', renderer='json', request_method='PUT')
@validated_form(name=String('name', min_length=3),
                username=String('username', min_length=3, max_length=16),
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
        return http_conflict(request,
                             'Username {0!r} already exists'.format(username))
    redir_location = request.route_path('session',
                                        _query={'username': username})
    return http_created(request, redir_location=redir_location)


@view_config(route_name='user_create', renderer='templates/user_create.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def user_edit(request):
    return {'page_title': 'Create User'}


@view_config(route_name='user_list', request_method='GET', permission='admin',
             renderer='templates/user_list.pt')
@site_layout('nudibranch:templates/layout.pt')
def user_list(request):
    session = Session()
    users = session.query(User).all()
    return {'page_title': 'User List', 'users': users}


@view_config(route_name='user_view',
             renderer='templates/user_view.pt',
             permission='authenticated')
@site_layout('nudibranch:templates/layout.pt')
def user_view(request):
    session = Session()
    person = User.fetch_by_name(request.matchdict['username'])
    return {'page_title': 'User Home',
            'username': person.name,
            'admin': person.is_admin}
