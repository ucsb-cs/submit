from __future__ import unicode_literals
import codecs
import os
import transaction
from base64 import b64decode
from hashlib import sha1
from pyramid_addons.helpers import (http_created, http_gone, http_ok,
                                    pretty_date, site_layout)
from pyramid_addons.validation import (Enum, List, String, RegexString,
                                       TextNumber, WhiteSpaceString, validate,
                                       SOURCE_GET,
                                       SOURCE_MATCHDICT as MATCHDICT)
from pyramid.httpexceptions import (HTTPBadRequest, HTTPConflict, HTTPError,
                                    HTTPForbidden, HTTPFound, HTTPNotFound,
                                    HTTPOk, HTTPRedirection, HTTPSeeOther)
from pyramid.response import FileResponse, Response
from pyramid.security import forget, remember
from pyramid.view import (forbidden_view_config, notfound_view_config,
                          view_config)
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message
from sqlalchemy.exc import IntegrityError
from .diff_render import HTMLDiff
from .exceptions import GroupWithException, InvalidId
from .helpers import (
    AccessibleDBThing, DBThing as AnyDBThing, DummyTemplateAttr,
    EditableDBThing, ViewableDBThing, clone, fetch_request_ids,
    file_verifier_verification, format_points, get_submission_stats,
    prepare_renderable, prev_next_submission, prev_next_group,
    project_file_create, project_file_delete, test_case_verification,
    zip_response)
from .models import (BuildFile, Class, ExecutionFile, File, FileVerifier,
                     Group, GroupRequest, PasswordReset, Project, Session,
                     Submission, SubmissionToFile, TestCase, Testable, User)


# A few reoccuring validators
OUTPUT_SOURCE = Enum('output_source', 'stdout', 'stderr', 'file')
OUTPUT_TYPE = Enum('output_type', 'diff', 'image', 'text')
SHA1_VALIDATOR = String('sha1sum', min_length=40, max_length=40,
                        source=MATCHDICT)
UUID_VALIDATOR = String('token', min_length=36, max_length=36,
                        source=MATCHDICT)


# We need a specific view config for each of HTTPError, HTTPOk, and
# HTTPRedirection as HTTPException will not work as a context. Because python
# has explicit decorators for forbidden and notfound (and we use them) we must
# also use those decorators here.
@forbidden_view_config(xhr=True, renderer='json')
@notfound_view_config(xhr=True, renderer='json')
@view_config(context=HTTPError, xhr=True, renderer='json')
@view_config(context=HTTPOk, xhr=True, renderer='json')
@view_config(context=HTTPRedirection, xhr=True, renderer='json')
def json_exception(context, request):
    """Always return json content in the body of Exceptions to xhr requests."""
    request.response.status = context.code
    return {'error': context._status, 'messages': context.message}


# Prevent PredicateMismatch exception
@view_config(context=HTTPError)
@view_config(context=HTTPOk)
@view_config(context=HTTPRedirection)
def normal_exception(context, request):
    """Just return the normal context"""
    return context


@forbidden_view_config()
def forbidden_view(context, request):
    if request.user:
        return context
    request.session.flash('You must be logged in to do that.')
    return HTTPSeeOther(request.route_path('session',
                                           _query={'dst': request.path}))


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


@view_config(route_name='robots', request_method='GET', http_cache=86400)
def robots(request):
    return Response(body='User-agent: *\nDisallow: /\n',
                    content_type=str('text/plain'))


@view_config(route_name='admin_utils', request_method='GET',
             permission='admin',
             renderer='templates/admin_utils.pt')
@site_layout('nudibranch:templates/layout.pt')
def admin_view(request):
    return {'page_title': 'Administrator Utilities'}


@view_config(route_name='build_file', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(file_=ViewableDBThing('file_id', File),
          filename=String('filename', min_length=1),
          project=EditableDBThing('project_id', Project))
def build_file_create(request, file_, filename, project):
    return project_file_create(request, file_, filename, project, BuildFile)


@view_config(route_name='build_file_item', request_method='DELETE',
             permission='authenticated', renderer='json')
@validate(build_file=EditableDBThing('build_file_id', BuildFile,
                                     source=MATCHDICT))
def build_file_delete(request, build_file):
    return project_file_delete(request, build_file)


@view_config(route_name='class_admin_utils', request_method='GET',
             permission='authenticated',
             renderer='templates/class_admin_utils.pt')
@site_layout('nudibranch:templates/layout.pt')
def class_admin_view(request):
    if not request.user.admin_for:
        raise HTTPForbidden()
    return {'page_title': 'Class Administrator Utilities'}


@view_config(route_name='class.admins', renderer='json', request_method='PUT')
@validate(class_=EditableDBThing('class_name', Class, fetch_by='name',
                                 validator=String('class_name'),
                                 source=MATCHDICT),
          user=AnyDBThing('email', User, fetch_by='username',
                          validator=String('email')))
def class_admins_add(request, class_, user):
    if user in class_.admins:
        raise HTTPConflict('That user is already an admin for the class.')
    session = Session()
    user.admin_for.append(class_)
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('The user could not be added.')
    request.session.flash('Added {} as an admin to the class.'.format(user))
    transaction.commit()
    return http_ok(request, redir_location=request.url)


@view_config(route_name='class.admins', request_method='GET',
             permission='authenticated',
             renderer='templates/class_admins.pt')
@validate(class_=EditableDBThing('class_name', Class, fetch_by='name',
                                 validator=String('class_name'),
                                 source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt',
             'nudibranch:templates/macros.pt')
def class_admins_view(request, class_):
    return {'page_title': 'Class Admins', 'class_': class_,
            'flash': request.session.pop_flash()}


@view_config(route_name='class', request_method='PUT', permission='admin',
             renderer='json')
@validate(name=String('name', min_length=3))
def class_create(request, name):
    session = Session()
    class_ = Class(name=name)
    session.add(class_)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('Class \'{0}\' already exists'.format(name))
    return http_created(request, redir_location=request.route_path('class'))


@view_config(route_name='class_new', renderer='templates/class_create.pt',
             request_method='GET', permission='admin')
@site_layout('nudibranch:templates/layout.pt')
def class_edit(request):
    return {'page_title': 'Create Class'}


@view_config(route_name='class_join_list', request_method='GET',
             permission='authenticated',
             renderer='templates/class_join_list.pt')
@site_layout('nudibranch:templates/layout.pt')
def class_join_list(request):
    # get all the classes that the given user is not in, and let the
    # user optionally join them
    all_classes = frozenset(Class.query_by(is_locked=False).all())
    user_classes = frozenset(request.user.classes)
    return {'page_title': 'Join Class',
            'classes': sorted(all_classes - user_classes)}


@view_config(route_name='class', request_method='GET',
             permission='authenticated', renderer='templates/class_list.pt')
@site_layout('nudibranch:templates/layout.pt')
def class_list(request):
    session = Session()
    classes = session.query(Class).all()
    return {'page_title': 'Login', 'classes': classes}


@view_config(route_name='class_item', request_method='GET',
             renderer='templates/class_view.pt', permission='authenticated')
@validate(class_=AnyDBThing('class_name', Class, fetch_by='name',
                            validator=String('class_name'), source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def class_view(request, class_):
    class_admin = class_.is_admin(request.user)
    projects = []
    if class_admin:
        for other in sorted(request.user.admin_for):
            projects.extend(other.projects)
    return {'page_title': 'Class Page', 'class_': class_,
            'class_admin': class_admin, 'projects': projects}


@view_config(route_name='execution_file', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(file_=ViewableDBThing('file_id', File),
          filename=String('filename', min_length=1),
          project=EditableDBThing('project_id', Project))
def execution_file_create(request, file_, filename, project):
    return project_file_create(request, file_, filename, project,
                               ExecutionFile)


@view_config(route_name='execution_file_item', request_method='DELETE',
             permission='authenticated', renderer='json')
@validate(execution_file=EditableDBThing('execution_file_id', ExecutionFile,
                                         source=MATCHDICT))
def execution_file_delete(request, execution_file):
    return project_file_delete(request, execution_file)


@view_config(route_name='file_item', request_method='PUT', renderer='json',
             permission='authenticated')
@validate(b64data=WhiteSpaceString('b64data'), sha1sum=SHA1_VALIDATOR)
def file_create(request, b64data, sha1sum):
    data = b64decode(b64data.encode('ascii'))
    # Verify the sha1 matches
    expected_sha1 = sha1(data).hexdigest()
    if sha1sum != expected_sha1:
        msg = 'sha1sum does not match expected: {0}'.format(expected_sha1)
        raise HTTPBadRequest(msg)

    # fetch or create (and save to disk) the file
    base_path = request.registry.settings['file_directory']
    file_ = File.fetch_or_create(data, base_path, sha1sum=sha1sum)

    # associate user with the file
    request.user.files.append(file_)
    session = Session()
    session.add(request.user)

    file_id = file_.id
    transaction.commit()
    return {'file_id': file_id}


@view_config(route_name='file_item_info', request_method='GET',
             permission='authenticated', renderer='json')
@validate(file_=ViewableDBThing('sha1sum', File, fetch_by='sha1',
                                validator=SHA1_VALIDATOR, source=MATCHDICT))
def file_item_info(request, file_):
    return {'file_id': file_.id, 'owns_file': file_ in request.user.files}


@view_config(route_name='file_item', request_method='GET',
             permission='authenticated', renderer='templates/file_view.pt')
@validate(file_=ViewableDBThing('sha1sum', File, fetch_by='sha1',
                                validator=SHA1_VALIDATOR, source=MATCHDICT),
          filename=String('filename', min_length=1, source=MATCHDICT),
          raw=TextNumber('raw', min_value=0, max_value=1,
                         optional=True, source=SOURCE_GET))
@site_layout('nudibranch:templates/layout.pt')
def file_item_view(request, file_, filename, raw):
    source = File.file_path(request.registry.settings['file_directory'],
                            file_.sha1)
    if raw:
        return FileResponse(source, request)
    try:
        contents = codecs.open(source, encoding='utf-8').read()
    except UnicodeDecodeError as exc:
        contents = 'File contents could not be displayed: {}'.format(exc)
    return {'page_title': filename,
            'contents': contents,
            'filename': filename,
            'css_files': ['highlight_github.css'],
            'javascripts': ['highlight.pack.js'],
            'url': request.route_path('file_item', sha1sum=file_.sha1,
                                      filename=filename, _query={'raw': '1'})}


@view_config(route_name='file_verifier', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(copy_to_execution=TextNumber('copy_to_execution', min_value=0,
                                       max_value=1, optional=True),
          filename=String('filename', min_length=1),
          min_size=TextNumber('min_size', min_value=0),
          max_size=TextNumber('max_size', min_value=0, optional=True),
          min_lines=TextNumber('min_lines', min_value=0),
          max_lines=TextNumber('max_lines', min_value=0, optional=True),
          optional=TextNumber('optional', min_value=0, max_value=1,
                              optional=True),
          project=EditableDBThing('project_id', Project),
          warning_regex=RegexString('warning_regex', optional=True))
@file_verifier_verification
def file_verifier_create(request, copy_to_execution, filename, min_size,
                         max_size, min_lines, max_lines, optional, project,
                         warning_regex):
    # Check for build-file conflict
    if not optional and BuildFile.fetch_by(project=project, filename=filename):
        msg = ('A build file already exists with that name. '
               'Provide a different name, or mark as optional.')
        raise HTTPBadRequest(msg)
    filev = FileVerifier(copy_to_execution=bool(copy_to_execution),
                         filename=filename, min_size=min_size,
                         max_size=max_size, min_lines=min_lines,
                         max_lines=max_lines, optional=bool(optional),
                         project=project, warning_regex=warning_regex)
    session = Session()
    session.add(filev)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That filename already exists for the project')

    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='file_verifier_item', request_method='DELETE',
             permission='authenticated', renderer='json')
@validate(file_verifier=EditableDBThing('file_verifier_id', FileVerifier,
                                        source=MATCHDICT))
def file_verifier_delete(request, file_verifier):
    return project_file_delete(request, file_verifier)


@view_config(route_name='file_verifier_item', request_method='POST',
             permission='authenticated', renderer='json')
@validate(copy_to_execution=TextNumber('copy_to_execution', min_value=0,
                                       max_value=1, optional=True),
          file_verifier=EditableDBThing('file_verifier_id', FileVerifier,
                                        source=MATCHDICT),
          filename=String('filename', min_length=1),
          min_size=TextNumber('min_size', min_value=0),
          max_size=TextNumber('max_size', min_value=0, optional=True),
          min_lines=TextNumber('min_lines', min_value=0),
          max_lines=TextNumber('max_lines', min_value=0, optional=True),
          optional=TextNumber('optional', min_value=0, max_value=1,
                              optional=True),
          warning_regex=RegexString('warning_regex', optional=True))
@file_verifier_verification
def file_verifier_update(request, copy_to_execution, file_verifier, filename,
                         min_size, max_size, min_lines, max_lines, optional,
                         warning_regex):
    # Check for build-file conflict
    if not optional and BuildFile.fetch_by(project=file_verifier.project,
                                           filename=filename):
        msg = ('A build file already exists with that name. '
               'Provide a different name, or mark as optional.')
        raise HTTPBadRequest(msg)
    if not file_verifier.update(copy_to_execution=bool(copy_to_execution),
                                filename=filename, min_size=min_size,
                                max_size=max_size, min_lines=min_lines,
                                max_lines=max_lines, optional=bool(optional),
                                warning_regex=warning_regex):
        return http_ok(request, message='Nothing to change')

    session = Session()
    session.add(file_verifier)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That filename already exists for the project')
    return http_ok(request, message='updated')


@view_config(route_name='home', renderer='templates/home.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def home(request):
    if request.user:
        url = request.route_path('user_item', username=request.user.username)
        raise HTTPFound(location=url)
    return {'page_title': 'Home'}


@view_config(route_name='password_reset', renderer='json',
             request_method='PUT')
@validate(username=String('email'))
def password_reset_create(request, username):
    if username == 'admin':
        raise HTTPConflict('Hahaha, nice try!')
    user = User.fetch_by(username=username)
    if not user:
        raise HTTPConflict('Invalid email')
    password_reset = PasswordReset.generate(user)
    failure_message = 'You were already sent a password reset email.'
    if password_reset:
        session = Session()
        session.add(password_reset)
        try:
            session.flush()
        except IntegrityError:
            transaction.abort()
            raise HTTPConflict(failure_message)
        site_name = request.registry.settings['site_name']
        reset_url = request.route_url('password_reset_item',
                                      token=password_reset.get_token())
        body = ('Visit the following link to reset your password:\n\n{0}'
                .format(reset_url))
        message = Message(subject='{0} password reset email'.format(site_name),
                          recipients=[user.username], body=body)
        get_mailer(request).send(message)
        transaction.commit()
        return http_ok(request,
                       message='A password reset link will be emailed to you.')
    else:
        raise HTTPConflict(failure_message)


@view_config(route_name='password_reset',
             renderer='templates/password_reset.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt',
             'nudibranch:templates/macros.pt')
def password_reset_edit(request):
    return {'page_title': 'Password Reset'}


@view_config(route_name='password_reset_item',
             renderer='templates/password_reset_item.pt',
             request_method='GET')
@validate(reset=AnyDBThing('token', PasswordReset, fetch_by='reset_token',
                           validator=UUID_VALIDATOR, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt',
             'nudibranch:templates/macros.pt')
def password_reset_edit_item(request, reset):
    return {'page_title': 'Password Reset',
            'token': reset.get_token()}


@view_config(route_name='password_reset_item', renderer='json',
             request_method='PUT')
@validate(username=String('email'),
          password=WhiteSpaceString('password', min_length=6),
          reset=AnyDBThing('token', PasswordReset, fetch_by='reset_token',
                           validator=UUID_VALIDATOR, source=MATCHDICT))
def password_reset_item(request, username, password, reset):
    if reset.user.username != username:
        raise HTTPConflict('The reset token and username '
                           'combination is not valid.')
    session = Session()
    reset.user.password = password
    session.add(reset.user)
    session.delete(reset)
    transaction.commit()
    return http_ok(request, message='Your password was changed successfully.')


@view_config(route_name='project_clone', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(class_=EditableDBThing('class_id', Class),
          src_project=ViewableDBThing('project_id', Project))
def project_clone(request, class_, src_project):
    # Build a copy of the project settings
    name = '(cloned) {0}: {1}'.format(src_project.class_.name,
                                      src_project.name)
    update = {'class_': class_, 'is_ready': False, 'name': name}
    project = clone(src_project, ('class_id',), update)

    session = Session()
    session.autoflush = False  # Don't flush while testing for changes

    # Copy project "files" keeping a mapping between src and dst objects
    mapping = {'build_files': {}, 'execution_files': {}, 'file_verifiers': {}}
    for attr in mapping:
        for item in getattr(src_project, attr):
            new = clone(item, ('project_id',))
            getattr(project, attr).append(new)
            mapping[attr][item] = new

    # Copy project testables
    for src_testable in src_project.testables:
        testable = clone(src_testable, ('project_id',))
        project.testables.append(testable)
        # Set testable "files" with the appropriate "new" file
        for attr, file_mapping in mapping.items():
            getattr(testable, attr).extend(file_mapping[x] for x
                                           in getattr(src_testable, attr))
        # Copy test cases
        testable.test_cases = [clone(x, ('testable_id',))
                               for x in src_testable.test_cases]
    session.add(project)
    try:
        session.flush()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('The name `{0}` already exists for the class.'
                           .format(name))
    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='project', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=2),
          class_=EditableDBThing('class_id', Class),
          makefile=ViewableDBThing('makefile_id', File, optional=True))
def project_create(request, name, class_, makefile):
    project = Project(name=name, class_=class_, makefile=makefile)
    session = Session()
    session.add(project)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That project name already exists for the class')
    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='project_item_download', request_method='GET',
             permission='authenticated')
@validate(project=ViewableDBThing('project_id', Project, source=MATCHDICT))
def project_download(request, project):
    def file_path(file_):
        return File.file_path(request.registry.settings['file_directory'],
                              file_.sha1)

    files = []
    for sub in project.recent_submissions():
        user_path = '{0}_{1}'.format(sub.group.users_str, sub.id)
        for filename, file_ in sub.file_mapping().items():
            files.append((os.path.join(project.name, user_path, filename),
                          file_path(file_)))
    return zip_response(request, project.name + '.zip', files)


@view_config(route_name='project_edit',
             renderer='templates/project_edit.pt',
             request_method='GET', permission='authenticated')
@validate(project=ViewableDBThing('project_id', Project, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_edit(request, project):
    action = request.route_path('project_item_summary',
                                class_name=project.class_.name,
                                project_id=project.id)
    return {'page_title': 'Edit Project', 'project': project, 'action': action,
            'flash': request.session.pop_flash()}


@view_config(route_name='project_group_item', renderer='json',
             request_method='PUT')
@validate(project=AccessibleDBThing('project_id', Project, source=MATCHDICT),
          group_request=EditableDBThing('group_request_id', GroupRequest,
                                        source=MATCHDICT))
def project_group_request_confirm(request, project, group_request):
    try:
        request.user.group_with(group_request.from_user, project)
        failed = False
    except GroupWithException as exc:
        request.session.flash(exc.args[0])
        failed = True

    try:
        Session.delete(group_request)
        Session.flush()
    except IntegrityError:
        raise HTTPConflict('Could not join the group at this time.')
    url = request.route_url('project_group', project_id=project.id)
    if failed:
        return http_gone(request, redir_location=url)
    request.session.flash('Joined group with {}'
                          .format(group_request.from_user))
    return http_ok(request, redir_location=url)


@view_config(route_name='project_group', renderer='json',
             request_method='PUT')
@validate(project=AccessibleDBThing('project_id', Project, source=MATCHDICT),
          username=String('email'))
def project_group_request_create(request, project, username):
    if not request.user.can_join_group(project):
        raise HTTPConflict('You cannot expand your group for this project.')
    user = User.fetch_by(username=username)
    if not user or project.class_ not in user.classes:
        raise HTTPConflict('Invalid email.')
    if not user.can_join_group(project):
        raise HTTPConflict('That user cannot join your group.')
    self_assoc = request.user.fetch_group_assoc(project)
    user_assoc = user.fetch_group_assoc(project)
    if self_assoc == user_assoc and self_assoc is not None:
        raise HTTPConflict('You are already in a group with that student.')

    session = Session()
    session.add(GroupRequest(from_user=request.user, project=project,
                             to_user=user))
    try:
        session.flush()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('Could not create your group request.')

    site_name = request.registry.settings['site_name']
    url = request.route_url('project_group', project_id=project.id)
    body = ('Your fellow {} student, {}, has requested you join their '
            'group for "{}". Please visit the following link to confirm or '
            'deny the request:\n\n{}'.format(
            project.class_.name, request.user, project.name, url))
    message = Message(subject='{}: {} "{}" Group Request'
                      .format(site_name, project.class_.name, project.name),
                      recipients=[user.username], body=body)
    get_mailer(request).send(message)
    request.session.flash('Request to {} sent via email.'.format(user))
    transaction.commit()
    return http_ok(request, redir_location=request.url)


@view_config(route_name='project_group_item', renderer='json',
             request_method='DELETE')
@validate(project=AccessibleDBThing('project_id', Project, source=MATCHDICT),
          group_request=AccessibleDBThing('group_request_id', GroupRequest,
                                          source=MATCHDICT))
def project_group_request_delete(request, project, group_request):
    if request.user == group_request.from_user:
        msg = 'Revoked request to {}.'.format(group_request.to_user)
    else:
        msg = 'Denied request from {}.'.format(group_request.from_user)
    Session.delete(group_request)
    request.session.flash(msg)
    url = request.route_url('project_group', project_id=project.id)
    return http_ok(request, redir_location=url)


@view_config(route_name='project_group', request_method='GET',
             renderer='templates/project_group.pt',
             permission='authenticated')
@validate(project=AccessibleDBThing('project_id', Project, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt',
             'nudibranch:templates/macros.pt')
def project_group_view(request, project):
    assoc = request.user.fetch_group_assoc(project)
    members = assoc.group.users_str if assoc else request.user.name
    pending = GroupRequest.query_by(project=project, to_user=request.user)
    requested = GroupRequest.query_by(from_user=request.user,
                                      project=project).first()
    can_join = request.user.can_join_group(project)
    return {'page_title': 'Group management', 'project': project,
            'members': members, 'can_join': can_join, 'pending': pending.all(),
            'requested': requested, 'flash': request.session.pop_flash()}


@view_config(route_name='project_info', request_method='GET',
             permission='authenticated', renderer='json')
@validate(project=EditableDBThing('project_id', Project, source=MATCHDICT))
def project_info(request, project):
    retval = {'id': project.id, 'name': project.name, 'testables': {}}
    for testable in project.testables:
        test_cases = {}
        for test_case in testable.test_cases:
            stdin = test_case.stdin.sha1 if test_case.stdin else None
            expected = test_case.expected.sha1 if test_case.expected else None
            test_cases[test_case.name] = {
                'id': test_case.id, 'args': test_case.args,
                'source': test_case.source,
                'stdin': stdin, 'expected': expected,
                'output_type': test_case.output_type,
                'output_filename': test_case.output_filename}
        retval['testables'][testable.name] = {'id': testable.id,
                                              'test_cases': test_cases}
    return retval


@view_config(route_name='project_new',
             renderer='templates/project_new.pt',
             request_method='GET', permission='authenticated')
@validate(class_=EditableDBThing('class_name', Class, fetch_by='name',
                                 validator=String('class_name'),
                                 source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_new(request, class_):
    dummy_project = DummyTemplateAttr(None)
    dummy_project.class_ = class_
    return {'page_title': 'Create Project', 'project': dummy_project}


@view_config(route_name='project_edit', renderer='json',
             request_method='PUT', permission='authenticated')
@validate(project=EditableDBThing('project_id', Project, source=MATCHDICT))
def project_requeue(request, project):
    count = 0
    for count, submission in enumerate(project.recent_submissions()):
        request.queue(submission_id=submission.id, _priority=2)
    request.session.flash('Requeued the most recent submissions ({0} items).'
                          .format(count))
    return http_ok(request, redir_location=request.url)


@view_config(route_name='project_item_summary', request_method='POST',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=2),
          makefile=ViewableDBThing('makefile_id', File, optional=True),
          is_ready=TextNumber('is_ready', min_value=0, max_value=1,
                              optional=True),
          class_name=String('class_name', source=MATCHDICT),
          delay_minutes=TextNumber('delay_minutes', min_value=0,
                                   optional=True, default=0),
          group_max=TextNumber('group_max', min_value=1),
          project=EditableDBThing('project_id', Project, source=MATCHDICT))
def project_update(request, name, makefile, is_ready, class_name,
                   delay_minutes, group_max, project):
    if project.class_.name != class_name:
        raise HTTPNotFound()
    if not project.update(name=name, makefile=makefile,
                          delay_minutes=delay_minutes,
                          group_max=group_max,
                          is_ready=bool(is_ready)):
        return http_ok(request, message='Nothing to change')
    project_id = project.id
    session = Session()
    session.add(project)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That project name already exists for the class')
    request.session.flash('Project updated')
    redir_location = request.route_path('project_edit',
                                        project_id=project_id)
    return http_ok(request, redir_location=redir_location)


@view_config(route_name='project_item_detailed',
             renderer='templates/project_view_detailed.pt',
             request_method=('GET', 'HEAD'),
             permission='authenticated')
@validate(class_name=String('class_name', source=MATCHDICT),
          project=AccessibleDBThing('project_id', Project, source=MATCHDICT),
          group=ViewableDBThing('group_id', Group, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_view_detailed(request, class_name, project, group):
    # Additional verification
    if project.class_.name != class_name:
        raise HTTPNotFound()
    submissions = Submission.query_by(project=project, group=group)
    if not submissions:
        raise HTTPNotFound()

    project_admin = project.can_view(request.user)
    if project_admin:
        prev_group, next_group = prev_next_group(project, group)
    else:
        prev_group = next_group = None

    return {'page_title': 'Project Page',
            'project': project,
            'project_admin': project_admin,
            'name': group.users_str,
            'can_edit': project_admin,
            'prev_group': prev_group,
            'next_group': next_group,
            'submissions': sorted(submissions,
                                  key=lambda s: s.created_at,
                                  reverse=True)}


@view_config(route_name='project_item_detailed_user',
             renderer='templates/project_view_detailed.pt',
             request_method=('GET', 'HEAD'),
             permission='authenticated')
@validate(class_name=String('class_name', source=MATCHDICT),
          project=AccessibleDBThing('project_id', Project, source=MATCHDICT),
          user=ViewableDBThing('username', User, fetch_by='username',
                               validator=String('username'), source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_view_detailed_user(request, class_name, project, user):
    group_assoc = user.fetch_group_assoc(project)
    if group_assoc:
        url = request.route_path('project_item_detailed',
                                 class_name=class_name, project_id=project.id,
                                 group_id=group_assoc.group_id)
        raise HTTPFound(location=url)
    return {'page_title': 'Project Page',
            'project': project,
            'project_admin': False,
            'name': user.name,
            'can_edit': False,
            'prev_group': None,
            'next_group': None,
            'submissions': []}


@view_config(route_name='project_item_stats',
             renderer='templates/project_stats.pt', permission='authenticated')
@validate(class_name=String('class_name', source=MATCHDICT),
          project=ViewableDBThing('project_id', Project, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_view_stats(request, class_name, project):
    # Additional verification
    if project.class_.name != class_name:
        raise HTTPNotFound()
    retval = get_submission_stats(Submission, project)
    retval['project'] = project
    return retval


@view_config(route_name='project_item_summary',
             renderer='templates/project_view_summary.pt',
             request_method=('GET', 'HEAD'),
             permission='authenticated')
@validate(class_name=String('class_name', source=MATCHDICT),
          project=ViewableDBThing('project_id', Project, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_view_summary(request, class_name, project):
    submissions = {}
    group_truncated = set()
    for group in project.groups:
        newest = (Submission.query_by(project=project, group=group)
                  .order_by(Submission.created_at.desc()).limit(4).all())
        if len(newest) == 4:
            group_truncated.add(group)
        submissions[group] = newest[:3]
    recent_submissions = (Submission.query_by(project=project)
                          .order_by(Submission.created_at.desc())
                          .limit(10).all())
    return {'page_title': 'Admin Project Page',
            'project': project,
            'group_truncated': group_truncated,
            'recent_submissions': recent_submissions,
            'submissions': sorted(submissions.items())}


@view_config(route_name='session', renderer='json', request_method='PUT')
@validate(username=String('email'), password=WhiteSpaceString('password'),
          dst=String('dst', optional=True))
def session_create(request, username, password, dst):
    user = User.login(username, password)
    if not user:
        raise HTTPConflict('Invalid login')
    headers = remember(request, user.id)
    if dst:
        url = dst
    else:
        url = request.route_path('user_item', username=user.username)
    return http_created(request, headers=headers, redir_location=url)


@view_config(route_name='session', renderer='json', request_method='DELETE',
             permission='authenticated')
def session_destroy(request):
    headers = forget(request)
    return http_gone(request, headers=headers,
                     redir_location=request.route_path('home'))


@view_config(route_name='session', renderer='templates/login.pt',
             request_method='GET')
@validate(username=String('username', optional=True, source=SOURCE_GET),
          dst=String('dst', optional=True, source=SOURCE_GET))
@site_layout('nudibranch:templates/layout.pt',
             'nudibranch:templates/macros.pt')
def session_edit(request, username, dst):
    return {'page_title': 'Login', 'username': username, 'dst': dst,
            'flash': request.session.pop_flash()}


@view_config(route_name='submission', renderer='json', request_method='PUT',
             permission='authenticated')
@validate(project=AccessibleDBThing('project_id', Project),
          file_ids=List('file_ids', TextNumber('', min_value=0),
                        min_elements=1),
          filenames=List('filenames', String('', min_length=1),
                         min_elements=1))
def submission_create(request, project, file_ids, filenames):
    # Additional input verification
    if len(file_ids) != len(filenames):
        msg = 'Number of file_ids must match number of filenames'
        raise HTTPBadRequest(msg)
    elif len(set(filenames)) != len(filenames):
        raise HTTPBadRequest('A filename cannot be provided more than once')

    # Verify user permission on files
    msgs = []
    user_file_ids = [x.id for x in request.user.files]
    for i, file_id in enumerate(file_ids):
        if file_id not in user_file_ids:
            msgs.append('Invalid file "{0}"'.format(filenames[i]))
    if msgs:
        raise HTTPBadRequest(msgs)

    submission = request.user.make_submission(project)
    assoc = []
    for file_id, filename in zip(file_ids, filenames):
        assoc.append(SubmissionToFile(file_id=file_id, filename=filename))
    submission.files.extend(assoc)
    session = Session()
    session.add(submission)
    session.add_all(assoc)
    session.flush()
    submission_id = submission.id
    transaction.commit()
    # Create the verification job
    request.queue(submission_id=submission_id)
    # Redirect to submission result page
    redir_location = request.route_path('submission_item',
                                        submission_id=submission_id)
    return http_created(request, redir_location=redir_location)


@view_config(route_name='submission_new', request_method='GET',
             renderer='templates/submission_new.pt',
             permission='authenticated')
@validate(project=AccessibleDBThing('project_id', Project, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt',
             'nudibranch:templates/macros.pt')
def submission_new(request, project):
    return {'page_title': 'Create submission', 'project': project}


@view_config(route_name='submission_item', renderer='json',
             request_method='PUT', permission='authenticated')
@validate(submission=EditableDBThing('submission_id', Submission,
                                     source=MATCHDICT))
def submission_requeue(request, submission):
    request.queue(submission_id=submission.id, _priority=0)
    request.session.flash('Requeued the submission')
    return http_ok(request, redir_location=request.url)


@view_config(route_name='submission_item', request_method='GET',
             renderer='templates/submission_view.pt',
             permission='authenticated')
@validate(submission=ViewableDBThing('submission_id', Submission,
                                     source=MATCHDICT),
          as_user=TextNumber('as_user', min_value=0, max_value=1,
                             optional=True, source=SOURCE_GET))
@site_layout('nudibranch:templates/layout.pt')
def submission_view(request, submission, as_user):
    submission_admin = (not bool(as_user) and
                        submission.project.can_edit(request.user))
    if not submission_admin:  # Only check delay for user view
        delay = submission.get_delay(
            update=request.user in submission.group.users)
        if delay:
            request.override_renderer = 'templates/submission_delay.pt'
            return {'_pd': pretty_date,
                    'delay': '{0:.1f} minutes'.format(delay),
                    'submission': submission}

    points_possible = submission.project.points_possible()
    if submission_admin:
        diff_renderer = HTMLDiff(num_reveal_limit=None,
                                 points_possible=points_possible)
    else:
        diff_renderer = HTMLDiff(points_possible=points_possible)

    for test_case_result in submission.test_case_results:
        diff_renderer.add_renderable(prepare_renderable(request,
                                                        test_case_result,
                                                        submission_admin))
    if submission.verification_results:
        extra_files = submission.extra_filenames
        verification_issues = submission.verification_results.issues()
        pending = submission.testables_pending()
        testable_statuses = submission.testable_statuses()
    else:
        extra_files = None
        verification_issues = None
        pending = None
        testable_statuses = []

    if submission.testables_completed() \
            - submission.testables_with_build_errors():
        # Decode utf-8 and ignore errors until the data is diffed in unicode.
        diff_table = diff_renderer.make_whole_file().decode('utf-8', 'ignore')
        points, _, _ = diff_renderer.tentative_score()
    else:
        points = 0
        diff_table = None

    # Update the session if necessary
    if points != submission.points \
            or points_possible != submission.points_possible:
        session = Session()
        submission.points = points
        submission.points_possible = points_possible
        session.add(submission)
        # Free items from the session that won't be modified
        session.expunge(request.user)
        for testable in submission.project.testables:
            session.expunge(testable)
        for testable_result in submission.testable_results:
            session.expunge(testable_result)
        try:
            transaction.commit()
        except IntegrityError:
            transaction.abort()
        # Re-associate objects with the new session
        session = Session()
        session.add(submission)

    # Do this after we've potentially updated the session
    if submission_admin:
        prev_sub, next_sub = prev_next_submission(submission)
        prev_group, next_group = prev_next_group(submission.project,
                                                 submission.group)
    else:
        prev_sub = next_sub = prev_group = next_group = None

    return {'page_title': 'Submission Page',
            '_pd': pretty_date,
            '_fp': format_points,
            'css_files': ['diff.css'],
            'diff_table': diff_table,
            'extra_files': extra_files,
            'flash': request.session.pop_flash(),
            'javascripts': ['diff.js'],
            'next_sub': next_sub,
            'next_group': next_group,
            'pending': pending,
            'prev_sub': prev_sub,
            'prev_group': prev_group,
            'submission': submission,
            'submission_admin': submission_admin,
            'testable_statuses': testable_statuses,
            'verification_issues': verification_issues}


@view_config(route_name='test_case', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=1),
          args=String('args', min_length=1),
          expected=ViewableDBThing('expected_id', File, optional=True),
          hide_expected=TextNumber('hide_expected', min_value=0, max_value=1,
                                   optional=True),
          output_filename=String('output_filename', min_length=1,
                                 optional=True),
          output_source=OUTPUT_SOURCE, output_type=OUTPUT_TYPE,
          points=TextNumber('points'),
          stdin=ViewableDBThing('stdin_id', File, optional=True),
          testable=EditableDBThing('testable_id', Testable))
@test_case_verification
def test_case_create(request, name, args, expected, hide_expected,
                     output_filename, output_source, output_type, points,
                     stdin, testable):
    test_case = TestCase(name=name, args=args, expected=expected,
                         hide_expected=bool(hide_expected),
                         output_filename=output_filename,
                         output_type=output_type, points=points,
                         source=output_source, stdin=stdin, testable=testable)
    session = Session()
    session.add(test_case)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That name already exists for the testable')
    redir_location = request.route_path('project_edit',
                                        project_id=testable.project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='test_case_item', request_method='DELETE',
             permission='authenticated', renderer='json')
@validate(test_case=EditableDBThing('test_case_id', TestCase,
                                    source=MATCHDICT))
def test_case_delete(request, test_case):
    redir_location = request.route_path(
        'project_edit', project_id=test_case.testable.project.id)
    request.session.flash('Deleted TestCase {0}.'.format(test_case.name))
    session = Session()
    session.delete(test_case)
    transaction.commit()
    return http_ok(request, redir_location=redir_location)


@view_config(route_name='test_case_item', request_method='POST',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=1),
          args=String('args', min_length=1),
          expected=ViewableDBThing('expected_id', File, optional=True),
          hide_expected=TextNumber('hide_expected', min_value=0, max_value=1,
                                   optional=True),
          output_filename=String('output_filename', min_length=1,
                                 optional=True),
          output_source=OUTPUT_SOURCE, output_type=OUTPUT_TYPE,
          points=TextNumber('points'),
          stdin=ViewableDBThing('stdin_id', File, optional=True),
          test_case=EditableDBThing('test_case_id', TestCase,
                                    source=MATCHDICT))
@test_case_verification
def test_case_update(request, name, args, expected, hide_expected,
                     output_filename, output_source, output_type, points,
                     stdin, test_case):
    if not test_case.update(name=name, args=args, expected=expected,
                            hide_expected=bool(hide_expected),
                            output_filename=output_filename,
                            output_type=output_type, points=points,
                            source=output_source, stdin=stdin):
        return http_ok(request, message='Nothing to change')
    session = Session()
    session.add(test_case)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That name already exists for the testable')
    return http_ok(request, message='Test case updated')


@view_config(route_name='testable', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=1),
          make_target=String('make_target', min_length=1, optional=True),
          executable=String('executable', min_length=1),
          build_file_ids=List('build_file_ids', TextNumber('', min_value=0),
                              optional=True),
          execution_file_ids=List('execution_file_ids',
                                  TextNumber('', min_value=0), optional=True),
          file_verifier_ids=List('file_verifier_ids',
                                 TextNumber('', min_value=0), optional=True),
          project=EditableDBThing('project_id', Project))
def testable_create(request, name, make_target, executable, build_file_ids,
                    execution_file_ids, file_verifier_ids, project):
    if make_target and not project.makefile:
        msg = 'make_target cannot be specified without a make file'
        raise HTTPBadRequest(msg)

    try:
        # Verify the ids actually exist and are associated with the project
        build_files = fetch_request_ids(build_file_ids, BuildFile,
                                        'build_file_id',
                                        project.build_files)
        execution_files = fetch_request_ids(execution_file_ids, ExecutionFile,
                                            'execution_file_id')
        file_verifiers = fetch_request_ids(file_verifier_ids, FileVerifier,
                                           'file_verifier_id',
                                           project.file_verifiers)
    except InvalidId as exc:
        raise HTTPBadRequest('Invalid {0}'.format(exc.message))

    testable = Testable(name=name, make_target=make_target,
                        executable=executable, project=project,
                        build_files=build_files,
                        execution_files=execution_files,
                        file_verifiers=file_verifiers)
    redir_location = request.route_path('project_edit', project_id=project.id)
    session = Session()
    session.add(testable)
    try:
        session.flush()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That name already exists for the project')
    testable_id = testable.id
    transaction.commit()
    return http_created(request, redir_location=redir_location,
                        testable_id=testable_id)


@view_config(route_name='testable_item', request_method='POST',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=1),
          make_target=String('make_target', min_length=1, optional=True),
          executable=String('executable', min_length=1),
          build_file_ids=List('build_file_ids', TextNumber('', min_value=0),
                              optional=True),
          execution_file_ids=List('execution_file_ids',
                                  TextNumber('', min_value=0), optional=True),
          file_verifier_ids=List('file_verifier_ids',
                                 TextNumber('', min_value=0), optional=True),
          testable=EditableDBThing('testable_id', Testable, source=MATCHDICT))
def testable_edit(request, name, make_target, executable, build_file_ids,
                  execution_file_ids, file_verifier_ids, testable):
    if make_target and not testable.project.makefile:
        msg = 'make_target cannot be specified without a make file'
        raise HTTPBadRequest(msg)

    try:
        # Verify the ids actually exist and are associated with the project
        build_files = fetch_request_ids(build_file_ids, BuildFile,
                                        'build_file_id',
                                        testable.project.build_files)
        execution_files = fetch_request_ids(execution_file_ids, ExecutionFile,
                                            'execution_file_id')
        file_verifiers = fetch_request_ids(file_verifier_ids, FileVerifier,
                                           'file_verifier_id',
                                           testable.project.file_verifiers)
    except InvalidId as exc:
        raise HTTPBadRequest('Invalid {0}'.format(exc.message))

    session = Session()
    session.autoflush = False  # Don't flush while testing for changes
    if not testable.update(_ignore_order=True, name=name,
                           make_target=make_target,
                           executable=executable,
                           build_files=build_files,
                           execution_files=execution_files,
                           file_verifiers=file_verifiers):
        return http_ok(request, message='Nothing to change')
    session.add(testable)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('That name already exists for the project')
    return http_ok(request, message='Testable updated')


@view_config(route_name='testable_item', request_method='DELETE',
             permission='authenticated', renderer='json')
@validate(testable=EditableDBThing('testable_id', Testable, source=MATCHDICT))
def testable_delete(request, testable):
    redir_location = request.route_path('project_edit',
                                        project_id=testable.project.id)
    request.session.flash('Deleted Testable {0}.'.format(testable.name))
    session = Session()
    session.delete(testable)
    transaction.commit()
    return http_ok(request, redir_location=redir_location)


@view_config(route_name='user_class_join', request_method='POST',
             permission='authenticated', renderer='json')
@validate(class_=AnyDBThing('class_name', Class, fetch_by='name',
                            validator=String('class_name'), source=MATCHDICT),
          username=String('username', min_length=6, max_length=64,
                          source=MATCHDICT))
def user_class_join(request, class_, username):
    if request.user.username != username:
        raise HTTPBadRequest('Invalid username')
    if class_.is_locked:
        raise HTTPBadRequest('Invalid class')
    request.user.classes.append(class_)
    redir_location = request.route_path('class_join_list',
                                        _query={'last_class': class_.name})
    session = Session()
    session.add(request.user)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='user', renderer='json', request_method='PUT')
@validate(name=String('name', min_length=3),
          username=String('email', min_length=6, max_length=64),
          password=WhiteSpaceString('password', min_length=6),
          admin_for=List('admin_for', EditableDBThing('', Class),
                         optional=True))
def user_create(request, name, username, password, admin_for):
    session = Session()
    user = User(name=name, username=username, password=password,
                is_admin=False)
    if admin_for:
        user.admin_for.extend(admin_for)
    session.add(user)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        raise HTTPConflict('User \'{0}\' already exists'.format(username))
    redir_location = request.route_path('session',
                                        _query={'username': username})
    return http_created(request, redir_location=redir_location)


@view_config(route_name='user_new', renderer='templates/user_create.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt',
             'nudibranch:templates/macros.pt')
def user_edit(request):
    admin_classes = request.user.classes_can_admin() if request.user else None
    return {'page_title': 'Create User',
            'admin_classes': admin_classes}


@view_config(route_name='user', request_method='GET', permission='admin',
             renderer='templates/user_list.pt')
@site_layout('nudibranch:templates/layout.pt')
def user_list(request):
    session = Session()
    users = session.query(User).all()
    return {'page_title': 'User List', 'users': users}


@view_config(route_name='user_item', request_method='GET',
             renderer='templates/user_view.pt', permission='authenticated')
@validate(user=ViewableDBThing('username', User, fetch_by='username',
                               validator=String('username'), source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def user_view(request, user):
    return {'page_title': 'User Page',
            'name': user.name,
            'classes_taking': sorted(user.classes),
            'admin_classes': user.classes_can_admin()}


@view_config(route_name='zipfile_download', request_method='GET',
             permission='authenticated')
@validate(submission=ViewableDBThing('submission_id', Submission,
                                     source=MATCHDICT))
def zipfile_download(request, submission):
    def file_path(file_):
        return File.file_path(request.registry.settings['file_directory'],
                              file_.sha1)
    base_path = '{0}_{1}'.format(submission.group.users_str, submission.id)
    # include makefile and student submitted files
    files = [(os.path.join(base_path, 'Makefile'),
              file_path(submission.project.makefile))]
    for filename, file_ in submission.file_mapping().items():
        files.append((os.path.join(base_path, filename), file_path(file_)))
    return zip_response(request, base_path + '.zip', files)
