import transaction
from sqlalchemy.exc import IntegrityError
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.response import Response
from pyramid.security import (Authenticated, authenticated_userid, forget,
                              remember)
from pyramid.view import notfound_view_config, view_config
from urllib.parse import urljoin
from .helpers import (http_conflict, http_created, http_gone, route_path,
                      site_layout, url_path)
from .models import Class, Session, User
from .validator import VString, VWSString, validated_form


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


@view_config(route_name='home', renderer='templates/home.pt',
             request_method='GET')
@site_layout
def home(request):
    user_id = authenticated_userid(request)
    if user_id:
        name = User.fetch_user_by_id(user_id).username
        return HTTPFound(location=route_path(request, 'user_view',
                                             username=name))
    return {'page_title': 'Home'}


@view_config(route_name='user', renderer='json', request_method='PUT')
@validated_form(name=VString('name', min_length=3),
                username=VString('username', min_length=3, max_length=16),
                password=VWSString('password', min_length=6),
                email=VString('email', min_length=6))
def user_create(request, name, username, password, email):
    admin = False
    session = Session()
    user = User(name=name, username=username, password=password,
                email=email, is_admin=admin)
    session.add(user)
    try:
        transaction.commit()
    except IntegrityError:
        return http_conflict(request,
                             'Username {0!r} already exists'.format(username))
    return http_created(request, redir_location=route_path(request, 'home'))


@view_config(route_name='user', renderer='templates/create_user.pt',
             request_method='GET')
@site_layout
def user_edit(request):
    return {'page_title': 'Create User'}


@view_config(route_name='session', renderer='json', request_method='PUT')
@validated_form(username=VString('username'),
                password=VWSString('password'))
def session_create(request, username, password):
    user = User.login(username, password)
    if user:
        headers = remember(request, user.id)
        url = route_path(request, 'user_view', username=user.username)
        retval = http_created(request, redir_location=url, headers=headers)
    else:
        retval = http_conflict(request, 'Invalid login.')
    return retval


@view_config(route_name='session', renderer='templates/login.pt',
             request_method='GET')
@site_layout
def session_edit(request):
    return {'page_title': 'Login'}


@view_config(route_name='session', renderer='json', request_method='DELETE',
             permission='authenticated')
def session_destroy(request):
    headers = forget(request)
    return http_gone(request, redir_location=route_path(request, 'home'),
                     headers=headers)


@view_config(route_name='user_view',
             renderer='templates/userhome.pt',
             permission='authenticated')
@site_layout
def user_view(request):
    session = Session()
    person = User.fetch_user_by_name(request.matchdict['username'])
    return {'page_title': 'User Home',
            'username': person.name,
            'admin': person.is_admin}


@view_config(route_name='class',
             renderer='templates/create_class.pt',
             permission='admin')
@site_layout
def create_class(request):
    failed = False
    message = []
    if 'submit' in request.POST:
        class_name = request.POST.get('Class_Name', '').strip()
        if class_name == '':
            failed = True
        else:
            session = Session()
            new_class = Class(class_name=class_name)
            message.append("Class added!")
            session.add(new_class)
            transaction.commit()
    return {'page_title': 'Create Class',
            'action_path': route_path(request, 'create_class'),
            'failed': failed,
            'message': message}


@view_config(route_name='class_view',
             permission='admin',
             renderer='templates/edit_class.pt')
@site_layout
def edit_class(request):
    session = Session()
    failed = False
    message = []
    for course in session.query(Class):
        message.append(course.class_name)

    if 'remove_submit' in request.POST:
        course_name = request.POST.get('Class_Name', '').strip()
        if course_name == '':
            failed = True
        else:
            to_remove = Class.fetch_class(course_name)
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
            rename = Class.fetch_class(old_name)
            if rename:
                rename.class_name = new_name
                message.remove(old_name)
                message.append(new_name)
                transaction.commit()
            else:
                failed = True

    return {'page_title': 'Edit Class',
            'action_path': route_path(request, 'edit_class'),
            'failed': failed,
            'message': message}
