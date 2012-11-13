from __future__ import unicode_literals
import json
import pickle
import pika
import transaction
from base64 import b64decode
from hashlib import sha1
from pyramid_addons.helpers import (http_bad_request, http_conflict,
                                    http_created, http_gone, http_ok,
                                    pretty_date, site_layout)
from pyramid_addons.validation import (List, String, TextNumber,
                                       WhiteSpaceString, validated_form)
from pyramid.httpexceptions import (HTTPException, HTTPForbidden, HTTPFound,
                                    HTTPNotFound)
from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.security import forget, remember
from pyramid.view import notfound_view_config, view_config
from sqlalchemy.exc import IntegrityError
from .helpers import DummyTemplateAttr, verify_file_ids
from .models import (Class, File, FileVerifier, Project, Session, Submission,
                     SubmissionToFile, TestCase, User)
from . import diff_render

@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


@view_config(route_name='class', request_method='PUT', permission='admin',
             renderer='json')
@validated_form(name=String('name', min_length=3))
def class_create(request, name):
    session = Session()
    klass = Class(name=name)
    session.add(klass)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request,
                             'Class \'{0}\' already exists'.format(name))
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
    klass = Class.fetch_by_name(request.matchdict['class_name'])
    if not klass:
        return HTTPNotFound()
    return {'page_title': 'Class Page', 'klass': klass}


@view_config(route_name='file_item', request_method='PUT', renderer='json',
             permission='authenticated')
@validated_form(b64data=WhiteSpaceString('b64data'))
def file_create(request, b64data):
    sha1sum = request.matchdict['sha1sum']
    data = b64decode(b64data.encode('ascii'))
    # Verify the sha1 matches
    expected_sha1 = sha1(data).hexdigest()
    if sha1sum != expected_sha1:
        msg = 'sha1sum does not match expected: {0}'.format(expected_sha1)
        return http_bad_request(request, msg)

    # fetch or create (and save to disk) the file
    base_path = request.registry.settings['file_directory']
    file = File.fetch_or_create(data, base_path, sha1sum=sha1sum)

    # associate user with the file
    request.user.files.append(file)
    session = Session()
    session.add(request.user)

    file_id = file.id
    transaction.commit()
    return {'file_id': file_id}


@view_config(route_name='file_item', request_method='GET',
             permission='authenticated', renderer='templates/file_view.pt')
@site_layout('nudibranch:templates/layout.pt')
def file_item_view(request):
    sha1sum = request.matchdict['sha1sum']
    if len(sha1sum) != 40:
        return http_bad_request(request, 'Invalid sha1sum')
    file = File.fetch_by_sha1(sha1sum)
    # return not found when the file has not been uploaded by the user
    if not file or file not in request.user.files:
        return HTTPNotFound()
    source = File.file_path(request.registry.settings['file_directory'],
                            sha1sum)
    contents = open(source).read()
    return {'page_title': 'File Contents', 'contents': contents}


@view_config(route_name='file_item_info', request_method='GET',
             permission='authenticated', renderer='json')
def file_item_info(request):
    sha1sum = request.matchdict['sha1sum']
    if len(sha1sum) != 40:
        return http_bad_request(request, 'Invalid sha1sum')
    file = File.fetch_by_sha1(sha1sum)
    # return not found when the file has not been uploaded by the user
    if not file or file not in request.user.files:
        return HTTPNotFound()
    return {'file_id': file.id}


@view_config(route_name='file_verifier', request_method='PUT',
             permission='admin', renderer='json')
@validated_form(filename=String('filename', min_length=1),
                min_size=TextNumber('min_size', min_value=0),
                max_size=TextNumber('max_size', min_value=0, optional=True),
                min_lines=TextNumber('min_lines', min_value=0),
                max_lines=TextNumber('max_lines', min_value=0, optional=True),
                project_id=TextNumber('project_id', min_value=0))
def file_verifier_create(request, filename, min_size, max_size, min_lines,
                         max_lines, project_id):
    # Additional verification
    if max_size is not None and max_size < min_size:
        return http_bad_request(request, 'min_size cannot be > max_size')
    if max_lines is not None and max_lines < min_lines:
        return http_bad_request(request, 'min_lines cannot be > max_lines')
    if min_size < min_lines:
        return http_bad_request(request, 'min_lines cannot be > min_size')
    if max_size is not None and max_lines is not None and max_size < max_lines:
        return http_bad_request(request, 'max_lines cannot be > max_size')

    session = Session()
    project = Project.fetch_by_id(project_id)
    if not project:
        return http_bad_request(request, 'Invalid project_id')

    filev = FileVerifier(filename=filename, min_size=min_size,
                         max_size=max_size, min_lines=min_lines,
                         max_lines=max_lines, project_id=project_id)
    session.add(filev)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        return http_conflict(request,
                             'That filename already exists for the project')

    redir_location = request.route_path('project_edit',
                                        project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='home', renderer='templates/home.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def home(request):
    if request.user:
        url = request.route_path('user_item', username=request.user.username)
        return HTTPFound(location=url)
    return {'page_title': 'Home'}


@view_config(route_name='project', request_method='PUT', permission='admin',
             renderer='json')
@validated_form(name=String('name', min_length=2),
                class_id=TextNumber('class_id', min_value=0),
                makefile_id=TextNumber('makefile_id', min_value=0,
                                       optional=True))
def project_create(request, name, class_id, makefile_id):
    session = Session()
    klass = Class.fetch_by_id(class_id)
    if not klass:
        return http_bad_request(request, 'Invalid class_id')
    id_check = verify_file_ids(request, makefile_id=makefile_id)
    if id_check:
        return id_check
    project = Project(name=name, class_id=class_id, makefile_id=makefile_id)
    session.add(project)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        return http_conflict(request,
                             'Project name already exists for the class')

    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='project_edit', renderer='templates/project_edit.pt',
             request_method='GET', permission='admin')
@site_layout('nudibranch:templates/layout.pt')
def project_edit(request):
    project = Project.fetch_by_id(request.matchdict['project_id'])
    if not project:
        return HTTPNotFound()
    action = request.route_path('project_item', class_name=project.klass.name,
                                project_id=project.id)
    return {'page_title': 'Edit Project', 'project': project, 'action': action}


@view_config(route_name='project_new', renderer='templates/project_new.pt',
             request_method='GET', permission='admin')
@site_layout('nudibranch:templates/layout.pt')
def project_new(request):
    klass = Class.fetch_by_name(request.matchdict['class_name'])
    if not klass:
        return HTTPNotFound()
    dummy_project = DummyTemplateAttr(None)
    dummy_project.klass = klass
    return {'page_title': 'Create Project', 'project': dummy_project}


@view_config(route_name='project_item', request_method='POST',
             permission='admin', renderer='json')
@validated_form(name=String('name', min_length=2),
                class_id=TextNumber('class_id', min_value=0),
                makefile_id=TextNumber('makefile_id', min_value=0,
                                       optional=True))
def project_update(request, name, class_id, makefile_id):
    project_id = request.matchdict['project_id']
    class_name = request.matchdict['class_name']
    project = Project.fetch_by_id(project_id)
    if not project:
        return http_bad_request(request, 'Invalid project_id')
    if class_id != project.klass.id or project.klass.name != class_name:
        return http_bad_request(request, 'Inconsistent class specification')

    changed = False
    if name != project.name:
        project.name = name
        changed = True
    if makefile_id != project.makefile_id:
        id_check = verify_file_ids(request, makefile_id=makefile_id)
        if id_check:
            return id_check
        project.makefile_id = makefile_id
        changed = True
    if not changed:
        return http_ok(request, 'Nothing to change')

    session = Session()
    session.add(project)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request,
                             'Project name already exists for the class')
    return http_ok(request, 'Project updated')


@view_config(route_name='project_item', request_method=('GET', 'HEAD'),
             permission='authenticated')
def project_view(request):
    project = Project.fetch_by_id(request.matchdict['project_id'])
    class_name = request.matchdict['class_name']
    if not project or project.klass.name != class_name:
        return HTTPNotFound()
    if request.user.is_admin:
        template = 'templates/project_view_admin.pt'
        retval = project_view_admin(request, project)
    else:
        template = 'templates/project_view_user.pt'
        retval = project_view_user(request, project)
    if isinstance(retval, HTTPException):
        return retval
    return render_to_response(template, retval, request)


@site_layout('nudibranch:templates/layout.pt')
def project_view_admin(request, project):
    submissions = {}
    for user in project.klass.users:
        submission = (Submission.fetch_by_user_project(user.id, project.id)
                      .order_by(Submission.created_at.desc())).first()
        submissions[user] = submission
    return {'page_title': 'Admin Project Page',
            'project': project,
            'submissions': sorted(submissions.items())}


@site_layout('nudibranch:templates/layout.pt')
def project_view_user(request, project):
    # Verify user is a member of the class
    if project.klass not in request.user.classes:
        return HTTPForbidden()

    submissions = Submission.fetch_by_user_project(request.user.id, project.id)
    if not submissions:
        return HTTPNotFound()

    return {'page_title': 'Project Page',
            'project': project,
            'submissions': sorted(submissions,
                                  key=lambda s: s.created_at,
                                  reverse=True)}


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


@view_config(route_name='submission', renderer='json', request_method='PUT',
             permission='authenticated')
@validated_form(project_id=TextNumber('project_id', min_value=0),
                file_ids=List('file_ids', TextNumber('', min_value=0),
                              min_elements=1),
                filenames=List('filenames', String('', min_length=1),
                               min_elements=1))
def submission_create(request, project_id, file_ids, filenames):
    # Additional input verification
    if len(file_ids) != len(filenames):
        return http_bad_request(request, ['# file_ids must match # filenames'])

    # Verify user permission on project and files
    session = Session()
    project = Project.fetch_by_id(project_id)
    msgs = []
    if not project:
        msgs.append('Invalid project_id')
    user_file_ids = [x.id for x in request.user.files]
    for i, file_id in enumerate(file_ids):
        if file_id not in user_file_ids:
            msgs.append('Invalid file "{0}"'.format(filenames[i]))
    if msgs:
        return http_bad_request(request, msgs)

    # Make a submission
    submission = Submission(project_id=project.id, user_id=request.user.id)
    assoc = []
    for file_id, filename in zip(file_ids, filenames):
        assoc.append(SubmissionToFile(file_id=file_id, filename=filename))
    submission.files.extend(assoc)
    session.add(submission)
    session.add_all(assoc)
    session.flush()
    submission_id = submission.id
    transaction.commit()
    # TODO: create a connection manager so we don't have to establish a
    # rabbitmq connection each time
    server = request.registry.settings['queue_server']
    queue = request.registry.settings['queue_verification']
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=server))
    channel = conn.channel()
    # Create the verification job (this will result in all future jobs)
    queue_msg = json.dumps({'submission_id': submission_id})
    channel.basic_publish(exchange='', body=queue_msg, routing_key=queue,
                          properties=pika.BasicProperties(delivery_mode=2))
    conn.close()
    # Redirect to submission result page
    redir_location = request.route_path('submission_item',
                                        submission_id=submission_id)
    return http_created(request, redir_location=redir_location)


@view_config(route_name='submission_item', request_method='GET',
             renderer='templates/submission_view.pt',
             permission='authenticated')
@site_layout('nudibranch:templates/layout.pt')
def submission_view(request):
    submission = Submission.fetch_by_id(request.matchdict['submission_id'])
    if not submission:
        return HTTPNotFound()

    # for each test case get the results, putting the diff into the diff
    # renderer.  Right now we just hardcode some things
    diff_renderer = diff_render.HTMLDiff()
    for test_case_result in submission.test_case_results:
        diff_file = File.file_path(request.registry.settings['file_directory'],
                                   test_case_result.diff.sha1)
        diff_renderer.add_diff(pickle.load(open(diff_file)))
    return {'page_title': 'Submission Page',
            'javascripts': ['diff.js'],
            'submission': submission,
            '_pd': pretty_date,
            'diff_table': diff_renderer.make_whole_file()}


@view_config(route_name='test_case', request_method='PUT', permission='admin',
             renderer='json')
@validated_form(name=String('name', min_length=1),
                args=String('args', min_length=1),
                expected_id=TextNumber('expected_id', min_value=0),
                points=TextNumber('points'),
                project_id=TextNumber('project_id', min_value=0),
                stdin_id=TextNumber('stdin_id', min_value=0, optional=True))
def test_case_create(request, name, args, expected_id, points, project_id,
                     stdin_id):
    session = Session()
    project = Project.fetch_by_id(project_id)
    if not project:
        return http_bad_request(request, 'Invalid project_id')
    id_check = verify_file_ids(request, expected_id=expected_id,
                               stdin_id=stdin_id)
    if id_check:
        return id_check
    test_case = TestCase(name=name, args=args, expected_id=expected_id,
                         points=points, project_id=project_id,
                         stdin_id=stdin_id)
    session.add(test_case)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        return http_conflict(request,
                             'That name already exists for the project')
    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


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
        transaction.abort()
        return http_conflict(request,
                             'User \'{0}\' already exists'.format(username))
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
    user = User.fetch_by_name(request.matchdict['username'])
    if not user:
        return HTTPNotFound()
    return {'page_title': 'User Page', 'user': user}
