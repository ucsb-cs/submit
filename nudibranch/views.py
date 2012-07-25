from pyramid.response import Response
from pyramid.view import notfound_view_config, view_config
from pyramid.security import authenticated_userid, forget, remember
from .helpers import site_layout, url_path, route_path
from urllib.parse import urljoin
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from .models import Session, User, Class
from .security import check_user
import transaction


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


@view_config(route_name='home', renderer='templates/home.pt')
@site_layout
def home(request):
    if authenticated_userid(request):
        name = User.fetch_user(authenticated_userid(request)).username
        return HTTPFound(location=route_path(request,
                                             'userhome',
                                             username=name))
    return {'page_title': 'Home'}


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
            if check_user(user, password):
                headers = remember(request, user)
                return HTTPFound(location=route_path(request, 'userhome',
                                                     username=user),
                                 headers=headers)
            else:
                failed = True
    return {'page_title': 'Login', 'action_path': route_path(request, 'login'),
            'failed': failed, 'user': user}


@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(location=route_path(request, 'home'),
                     headers=headers)


@view_config(route_name='userhome',
             renderer='templates/userhome.pt',
             permission='student')
@site_layout
def userhome(request):
    session = Session()
    person = User.fetch_user(request.matchdict['username'])
    return {'page_title': 'User Home',
            'username': person.name,
            'admin': person.is_admin}


@view_config(route_name='create_user', renderer='templates/create_user.pt')
@site_layout
def create_user(request):
    failed = False
    username = ''
    if 'submit' in request.POST:
        user = request.POST.get('Username', '').strip()
        name = request.POST.get('Name', '').strip()
        password = request.POST.get('Password', '').strip()
        email = request.POST.get('Email', '').strip()
        admin = False
        if (user == '') or (password == '') or (email == '') or (name == ''):
            failed = True
        else:
            session = Session()
            new_user = User(name=name,
                            email=email,
                            username=user,
                            password=password,
                            is_admin=admin)
            session.add(new_user)
            transaction.commit()
            headers = remember(request, user.id)
            return HTTPFound(location=route_path(request,
                                                 'userhome',
                                                 username=user),
                             headers=headers)

    return {'page_title': 'Create User',
            'action_path': route_path(request, 'create_user'),
            'failed': failed}


@view_config(route_name='create_class',
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


@view_config(route_name='edit_class',
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
