from __future__ import unicode_literals
import codecs
import pickle
import transaction
from base64 import b64decode
from hashlib import sha1
from pyramid_addons.helpers import (http_bad_request, http_conflict,
                                    http_created, http_gone, http_ok,
                                    pretty_date, site_layout)
from pyramid_addons.validation import (Enum, List, String, RegexString,
                                       TextNumber, WhiteSpaceString, validate,
                                       SOURCE_GET,
                                       SOURCE_MATCHDICT as MATCHDICT)
from pyramid.httpexceptions import HTTPForbidden, HTTPFound, HTTPNotFound
from pyramid.response import FileResponse, Response
from pyramid.security import forget, remember
from pyramid.view import notfound_view_config, view_config
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message
from sqlalchemy.exc import IntegrityError
from .diff_render import HTMLDiff
from .diff_unit import Diff, DiffWithMetadata, DiffExtraInfo
from .exceptions import InvalidId
from .helpers import (DBThing as AnyDBThing, DummyTemplateAttr,
                      EditableDBThing, ViewableDBThing, get_submission_stats,
                      fetch_request_ids, prev_next_submission, prev_next_user)
from .models import (BuildFile, Class, ExecutionFile, File, FileVerifier,
                     PasswordReset, Project, Session, Submission,
                     SubmissionToFile, TestCase, Testable, User)
from .zipper import ZipSubmission


# A few reoccuring validators
OUTPUT_SOURCE = Enum('output_source', 'stdout', 'stderr', 'file')
OUTPUT_TYPE = Enum('output_type', 'diff', 'image', 'text')
SHA1_VALIDATOR = String('sha1sum', min_length=40, max_length=40,
                        source=MATCHDICT)
UUID_VALIDATOR = String('token', min_length=36, max_length=36,
                        source=MATCHDICT)


@notfound_view_config()
def not_found(request):
    return Response('Not Found', status='404 Not Found')


def project_file_create(request, file_, filename, project, cls):
    # Check for BuildFile and FileVerifier conflict
    if cls == BuildFile and FileVerifier.fetch_by(project_id=project.id,
                                                  filename=filename,
                                                  optional=False):
        return http_bad_request(request, messages=('A required expected file '
                                                   'already exists with that '
                                                   'name.'))
    cls_file = cls(file=file_, filename=filename, project=project)
    session = Session()
    session.add(cls_file)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('That filename already exists '
                                               'for the project'))
    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    request.session.flash('Added {0} {1}.'.format(cls.__name__, filename))
    return http_created(request, redir_location=redir_location)


def project_file_delete(request, project_file):
    redir_location = request.route_path('project_edit',
                                        project_id=project_file.project.id)
    request.session.flash('Deleted {0} {1}.'
                          .format(project_file.__class__.__name__,
                                  project_file.filename))
    # Delete the file
    session = Session()
    session.delete(project_file)
    transaction.commit()
    return http_ok(request, redir_location=redir_location)


def test_case_verification(function):
    def wrapped(request, expected, output_filename, output_source, output_type,
                *args, **kwargs):
        msgs = []
        if output_filename and output_source != 'file':
            msgs.append('output_filename can only be set when the source '
                        'is a named file')
        elif not output_filename and output_source == 'file':
            msgs.append('output_filename must be set when the source is a '
                        'named file')
        if expected and output_type != 'diff':
            msgs.append('expected_id can only be set when the type is diff')
        elif not expected and output_type == 'diff':
            msgs.append('expected_id must be set when the type is diff')
        if msgs:
            return http_bad_request(request, messages=msgs)
        return function(request, *args, expected=expected,
                        output_filename=output_filename,
                        output_source=output_source, output_type=output_type,
                        **kwargs)
    return wrapped


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


@view_config(route_name='class', request_method='PUT', permission='admin',
             renderer='json')
@validate(name=String('name', min_length=3))
def class_create(request, name):
    session = Session()
    klass = Class(name=name)
    session.add(klass)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('Class \'{0}\' already exists'
                                               .format(name)))
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
    all_classes = frozenset(Session().query(Class).all())
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
    return {'page_title': 'Class Page',
            'class_admin': class_.can_edit(request.user), 'klass': class_}


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
        return http_bad_request(request, messages=msg)

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
@validate(file_=ViewableDBThing('sha1sum', File, fetch_by='sha1',
                                validator=SHA1_VALIDATOR, source=MATCHDICT),
          filename=String('filename', min_length=1, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def file_item_view(request, file_, filename):
    source = File.file_path(request.registry.settings['file_directory'],
                            file_.sha1)
    contents = codecs.open(source, encoding='utf-8').read()
    return {'page_title': filename,
            'contents': contents,
            'filename': filename,
            'css_files': ['highlight_github.css'],
            'javascripts': ['highlight.pack.js']}


@view_config(route_name='file_item_info', request_method='GET',
             permission='authenticated', renderer='json')
@validate(file_=ViewableDBThing('sha1sum', File, fetch_by='sha1',
                                validator=SHA1_VALIDATOR, source=MATCHDICT))
def file_item_info(request, file_):
    return {'file_id': file_.id}


@view_config(route_name='file_verifier', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(filename=String('filename', min_length=1),
          min_size=TextNumber('min_size', min_value=0),
          max_size=TextNumber('max_size', min_value=0, optional=True),
          min_lines=TextNumber('min_lines', min_value=0),
          max_lines=TextNumber('max_lines', min_value=0, optional=True),
          optional=TextNumber('optional', min_value=0, max_value=1,
                              optional=True),
          project=EditableDBThing('project_id', Project),
          warning_regex=RegexString('warning_regex', optional=True))
def file_verifier_create(request, filename, min_size, max_size, min_lines,
                         max_lines, optional, project, warning_regex):
    if max_size is not None and max_size < min_size:
        return http_bad_request(request,
                                messages='min_size cannot be > max_size')
    if max_lines is not None and max_lines < min_lines:
        return http_bad_request(request,
                                messages='min_lines cannot be > max_lines')
    if min_size < min_lines:
        return http_bad_request(request,
                                messages='min_lines cannot be > min_size')
    if max_size is not None and max_lines is not None and max_size < max_lines:
        return http_bad_request(request,
                                messages='max_lines cannot be > max_size')
    # Check for build-file conflict
    if not optional and BuildFile.fetch_by(project=project, filename=filename):
        return http_bad_request(request, messages=('A build file already '
                                                   'exists with that name. '
                                                   'Provide a different name, '
                                                   'or mark as optional.'))

    filev = FileVerifier(filename=filename, min_size=min_size,
                         max_size=max_size, min_lines=min_lines,
                         max_lines=max_lines, optional=bool(optional),
                         project=project, warning_regex=warning_regex)
    session = Session()
    session.add(filev)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('That filename already exists '
                                               'for the project'))

    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='file_verifier_item', request_method='DELETE',
             permission='authenticated', renderer='json')
def file_verifier_delete(request):
    return project_file_delete(request, 'file_verifier_id', FileVerifier)


@view_config(route_name='file_verifier_item', request_method='POST',
             permission='authenticated', renderer='json')
@validate(file_verifier=EditableDBThing('file_verifier_id', FileVerifier,
                                        source=MATCHDICT),
          filename=String('filename', min_length=1),
          min_size=TextNumber('min_size', min_value=0),
          max_size=TextNumber('max_size', min_value=0, optional=True),
          min_lines=TextNumber('min_lines', min_value=0),
          max_lines=TextNumber('max_lines', min_value=0, optional=True),
          optional=TextNumber('optional', min_value=0, max_value=1,
                              optional=True),
          warning_regex=RegexString('warning_regex', optional=True))
def file_verifier_update(request, file_verifier, filename, min_size, max_size,
                         min_lines, max_lines, optional, warning_regex):
    # Additional verification
    if max_size is not None and max_size < min_size:
        return http_bad_request(request,
                                messages='min_size cannot be > max_size')
    if max_lines is not None and max_lines < min_lines:
        return http_bad_request(request,
                                messages='min_lines cannot be > max_lines')
    if min_size < min_lines:
        return http_bad_request(request,
                                messages='min_lines cannot be > min_size')
    if max_size is not None and max_lines is not None and max_size < max_lines:
        return http_bad_request(request,
                                messages='max_lines cannot be > max_size')
    # Check for build-file conflict
    if not optional and BuildFile.fetch_by(project_id=file_verifier.project_id,
                                           filename=filename):
        return http_bad_request(request, messages=('A build file already '
                                                   'exists with that name. '
                                                   'Provide a different name, '
                                                   'or mark as optional.'))

    if not file_verifier.update(filename=filename, min_size=min_size,
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
        return http_conflict(request, message=('That filename already exists '
                                               'for the project'))
    return http_ok(request, message='updated')


@view_config(route_name='home', renderer='templates/home.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def home(request):
    if request.user:
        url = request.route_path('user_item', username=request.user.username)
        return HTTPFound(location=url)
    return {'page_title': 'Home'}


@view_config(route_name='password_reset', renderer='json',
             request_method='PUT')
@validate(username=String('email'))
def password_reset_create(request, username):
    if username == 'admin':
        return http_conflict(request, message='Hahaha, nice try!')
    user = User.fetch_by(username=username)
    if not user:
        return http_conflict(request, message='Invalid email')
    password_reset = PasswordReset.generate(user)

    failure_message = 'You were already sent a password reset email.'

    if password_reset:
        session = Session()
        session.add(password_reset)
        try:
            session.flush()
        except IntegrityError:
            transaction.abort()
            return http_conflict(request, message=failure_message)
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
        return http_conflict(request, message=failure_message)


@view_config(route_name='password_reset',
             renderer='templates/password_reset.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def password_reset_edit(request):
    return {'page_title': 'Password Reset'}


@view_config(route_name='password_reset_item', renderer='json',
             request_method='PUT')
@validate(username=String('email'),
          password=WhiteSpaceString('password', min_length=6),
          reset=AnyDBThing('token', PasswordReset, fetch_by='reset_token',
                           validator=UUID_VALIDATOR, source=MATCHDICT))
def password_reset_item(request, username, password, reset):
    if reset.user.username != username:
        return http_conflict(request, message=('The reset token and username '
                                               'combination is not valid.'))
    session = Session()
    reset.user.password = password
    session.add(reset.user)
    session.delete(reset)
    transaction.commit()
    return http_ok(request, message='Your password was changed successfully.')


@view_config(route_name='password_reset_item',
             renderer='templates/password_reset_item.pt',
             request_method='GET')
@validate(reset=AnyDBThing('token', PasswordReset, fetch_by='reset_token',
                           validator=UUID_VALIDATOR, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def password_reset_edit_item(request, reset):
    return {'page_title': 'Password Reset',
            'token': reset.get_token()}


@view_config(route_name='project', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=2),
          class_=EditableDBThing('class_id', Class),
          makefile=ViewableDBThing('makefile_id', File, optional=True))
def project_create(request, name, class_, makefile):
    project = Project(name=name, klass=class_, makefile=makefile)
    session = Session()
    session.add(project)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('Project name already exists '
                                               'for the class'))

    redir_location = request.route_path('project_edit', project_id=project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='project_edit',
             renderer='templates/project_edit.pt',
             request_method='GET', permission='authenticated')
@validate(project=EditableDBThing('project_id', Project, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_edit(request, project):
    action = request.route_path('project_item_summary',
                                class_name=project.klass.name,
                                project_id=project.id)
    return {'page_title': 'Edit Project', 'project': project, 'action': action,
            'flash': request.session.pop_flash()}


@view_config(route_name='project_new',
             renderer='templates/project_new.pt',
             request_method='GET', permission='authenticated')
@validate(class_=EditableDBThing('class_name', Class, fetch_by='name',
                                 validator=String('class_name'),
                                 source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_new(request, class_):
    dummy_project = DummyTemplateAttr(None)
    dummy_project.klass = class_
    return {'page_title': 'Create Project', 'project': dummy_project}


@view_config(route_name='project_edit', renderer='json',
             request_method='PUT', permission='authenticated')
@validate(project=EditableDBThing('project_id', Project, source=MATCHDICT))
def project_requeue(request, project):
    items = 0
    for user in project.klass.users:
        submission = Submission.most_recent_submission(project.id, user.id)
        if submission:
            request.queue(submission_id=submission.id, _priority=2)
            items += 1
    request.session.flash('Requeued the most recent submissions ({0} items).'
                          .format(items))
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
          project=EditableDBThing('project_id', Project, source=MATCHDICT))
def project_update(request, name, makefile, is_ready, class_name,
                   delay_minutes, project):
    if project.klass.name != class_name:
        raise HTTPNotFound()
    if not project.update(name=name, makefile=makefile,
                          delay_minutes=delay_minutes,
                          is_ready=bool(is_ready)):
        return http_ok(request, message='Nothing to change')
    project_id = project.id
    session = Session()
    session.add(project)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('Project name already exists '
                                               'for the class'))
    request.session.flash('Project updated')
    redir_location = request.route_path('project_edit',
                                        project_id=project_id)
    return http_ok(request, redir_location=redir_location)


@view_config(route_name='project_item_stats',
             renderer='templates/project_stats.pt', permission='authenticated')
@validate(class_name=String('class_name', source=MATCHDICT),
          project=EditableDBThing('project_id', Project, source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_view_stats(request, class_name, project):
    # Additional verification
    if project.klass.name != class_name:
        raise HTTPNotFound()
    retval = get_submission_stats(Submission, project)
    retval['project'] = project
    return retval


@view_config(route_name='project_item_detailed',
             renderer='templates/project_view_detailed.pt',
             request_method=('GET', 'HEAD'),
             permission='authenticated')
@validate(class_name=String('class_name', source=MATCHDICT),
          project=ViewableDBThing('project_id', Project, source=MATCHDICT),
          user=ViewableDBThing('username', User, fetch_by='username',
                               validator=String('username'), source=MATCHDICT))
@site_layout('nudibranch:templates/layout.pt')
def project_view_detailed(request, class_name, project, user):
    # Additional verification
    if project.klass.name != class_name:
        raise HTTPNotFound()
    submissions = Submission.query_by(project_id=project.id, user_id=user.id)
    if not submissions:
        raise HTTPNotFound()

    project_admin = project.can_edit(request.user)
    if project_admin:
        prev_user, next_user = prev_next_user(project, user)
    else:
        prev_user, next_user = None

    # Build submission file string
    required = []
    optional = []
    for file_verifier in project.file_verifiers:
        if file_verifier.optional:
            optional.append('[{0}]'.format(file_verifier.filename))
        else:
            required.append(file_verifier.filename)
    submit_string = ' '.join(sorted(required) + sorted(optional))

    return {'page_title': 'Project Page',
            'project': project,
            'project_admin': project_admin,
            'name': user.name,
            'can_edit': project_admin,
            'prev_user': prev_user,
            'next_user': next_user,
            'submissions': sorted(submissions,
                                  key=lambda s: s.created_at,
                                  reverse=True),
            'submit_string': submit_string}


@view_config(route_name='project_item_summary',
             renderer='templates/project_view_summary.pt',
             request_method=('GET', 'HEAD'),
             permission='authenticated')
@site_layout('nudibranch:templates/layout.pt')
def project_view_summary(request):
    class_name = request.matchdict['class_name']
    project = Project.fetch_by_id(request.matchdict['project_id'])
    if not project or project.klass.name != class_name:
        return HTTPNotFound()

    if not project.can_edit(request.user):
        return HTTPForbidden()

    submissions = {}
    user_truncated = set()
    for user in project.klass.users:
        newest = (Submission.query_by(project=project, user=user)
                  .order_by(Submission.created_at.desc()).limit(4).all())
        if len(newest) == 4:
            user_truncated.add(user)
        submissions[user] = newest[:3]
    return {'page_title': 'Admin Project Page',
            'project': project,
            'user_truncated': user_truncated,
            'submissions': sorted(submissions.items())}


@view_config(route_name='session', renderer='json', request_method='PUT')
@validate(username=String('email'), password=WhiteSpaceString('password'))
def session_create(request, username, password):
    user = User.login(username, password)
    if user:
        headers = remember(request, user.id)
        url = request.route_path('user_item',
                                 username=user.username)
        retval = http_created(request, headers=headers, redir_location=url)
    else:
        retval = http_conflict(request, message='Invalid login')
    return retval


@view_config(route_name='session', renderer='json', request_method='DELETE',
             permission='authenticated')
def session_destroy(request):
    headers = forget(request)
    return http_gone(request, headers=headers,
                     redir_location=request.route_path('home'))


@view_config(route_name='session', renderer='templates/login.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def session_edit(request):
    username = request.GET.get('username', '')
    return {'page_title': 'Login', 'username': username}


@view_config(route_name='submission', renderer='json', request_method='PUT',
             permission='authenticated')
@validate(project_id=TextNumber('project_id', min_value=0),
          file_ids=List('file_ids', TextNumber('', min_value=0),
                        min_elements=1),
          filenames=List('filenames', String('', min_length=1),
                         min_elements=1))
def submission_create(request, project_id, file_ids, filenames):
    # Additional input verification
    if len(file_ids) != len(filenames):
        return http_bad_request(request,
                                messages='# file_ids must match # filenames')

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
        return http_bad_request(request, messages=msgs)

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
    # Create the verification job
    request.queue(submission_id=submission_id)
    # Redirect to submission result page
    redir_location = request.route_path('submission_item',
                                        submission_id=submission_id)
    return http_created(request, redir_location=redir_location)


@view_config(route_name='zipfile_download', request_method='GET',
             permission='authenticated')
@validate(submission=ViewableDBThing('submission_id', Submission,
                                     source=MATCHDICT))
def zipfile_download(request, submission):
    with ZipSubmission(submission, request) as zipfile:
        response = FileResponse(
            zipfile.actual_filename(),
            content_type=str('application/zip'))
        disposition = str('attachment; filename="{0}"'
                          .format(zipfile.pretty_filename()))
        response.headers[str('Content-disposition')] = disposition
        return response


def format_points(points):
    return "({0} {1})".format(
        points,
        "point" if points == 1 else "points")


def problem_files_header(files, test_cases):
    from .helpers import escape
    formatted = ", ".join(
        ["'<code>{0}</code>'".format(escape(file))
         for file in files])
    score = sum([test.points for test in test_cases])
    template = "<h3 style=\"color:red\">{0} {1}: {2} {3}</h3>"
    return template.format(
        "Failed tests due to problems with",
        "this file" if len(files) == 1 else "these files",
        formatted,
        format_points(score))


def to_full_diff(request, test_case_result):
    '''Given a test case result, it will return a complete DiffWithMetadata
    object, or None if we couldn't get the test case'''

    try:
        diff_file = File.file_path(request.registry.settings['file_directory'],
                                   test_case_result.diff.sha1)
        diff = pickle.load(open(diff_file))
    except (AttributeError, EOFError):
        diff = Diff(['submit system mismatch -- requeue submission\n'], [])
    test_case = TestCase.fetch_by_id(test_case_result.test_case_id)
    if not test_case:
        return None
    testable = Testable.fetch_by_id(test_case.testable_id)
    if not testable:
        return None
    return DiffWithMetadata(diff,
                            test_case.id,
                            testable.name,
                            test_case.name,
                            test_case.points,
                            DiffExtraInfo(test_case_result.status,
                                          test_case_result.extra))


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
        delay = submission.get_delay(update=submission.user == request.user)
        if delay:
            request.override_renderer = 'templates/submission_delay.pt'
            return {'_pd': pretty_date,
                    'delay': '{0:.1f} minutes'.format(delay),
                    'submission': submission}

    points_possible = submission.project.points_possible()
    if submission_admin:
        prev_sub, next_sub = prev_next_submission(submission)
        prev_user, next_user = prev_next_user(submission.project,
                                              submission.user)
        try:
            diff_renderer = HTMLDiff(num_reveal_limit=None,
                                     points_possible=points_possible)
        except InvalidId:
            return HTTPNotFound()
    else:
        diff_renderer = HTMLDiff(points_possible=points_possible)
        prev_sub = next_sub = prev_user = next_user = None

    for test_case_result in submission.test_case_results:
        if test_case_result.test_case.output_type == 'diff':
            full_diff = to_full_diff(request, test_case_result)
            if not full_diff:
                return HTTPNotFound()
            diff_renderer.add_diff(full_diff)
        else:  # Handle text or image output
            print('Other output type: {0}'
                  .format(test_case_result.test_case.source))
            if test_case_result.diff:
                output_file = File.file_path(
                    request.registry.settings['file_directory'],
                    test_case_result.diff.sha1)
                print(open(output_file).read())
            else:
                print('No output file captured.')

    verification_info = submission.verification_warnings_errors()
    waiting_to_run = submission.testables_waiting_to_run()
    testable_statuses = submission.testable_statuses()
    extra_files = submission.extra_filenames()

    # Decode utf-8 and ignore errors until the data is diffed in unicode.
    diff_table = diff_renderer.make_whole_file().decode('utf-8', 'ignore')
    return {'page_title': 'Submission Page',
            '_pd': pretty_date,
            '_fp': format_points,
            'css_files': ['diff.css'],
            'diff_table': diff_table,
            'extra_files': extra_files,
            'flash': request.session.pop_flash(),
            'javascripts': ['diff.js'],
            'next_sub': next_sub,
            'next_user': next_user,
            'prev_sub': prev_sub,
            'prev_user': prev_user,
            'submission': submission,
            'submission_admin': submission_admin,
            'testable_statuses': testable_statuses,
            'verification': verification_info,
            'waiting_to_run': waiting_to_run}


@view_config(route_name='test_case', request_method='PUT',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=1),
          args=String('args', min_length=1),
          expected=ViewableDBThing('expected_id', File, optional=True),
          output_filename=String('output_filename', min_length=1,
                                 optional=True),
          output_source=OUTPUT_SOURCE, output_type=OUTPUT_TYPE,
          points=TextNumber('points'),
          stdin=ViewableDBThing('stdin_id', File, optional=True),
          testable=EditableDBThing('testable_id', Testable))
@test_case_verification
def test_case_create(request, name, args, expected, output_filename,
                     output_source, output_type, points, stdin, testable):
    test_case = TestCase(name=name, args=args, expected=expected,
                         output_filename=output_filename,
                         output_type=output_type, points=points,
                         source=output_source, stdin=stdin, testable=testable)
    session = Session()
    session.add(test_case)
    try:
        session.flush()  # Cannot commit the transaction here
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('That name already exists for '
                                               'the testable'))
    redir_location = request.route_path('project_edit',
                                        project_id=testable.project.id)
    transaction.commit()
    return http_created(request, redir_location=redir_location)


@view_config(route_name='test_case_item', request_method='POST',
             permission='authenticated', renderer='json')
@validate(name=String('name', min_length=1),
          args=String('args', min_length=1),
          expected=ViewableDBThing('expected_id', File, optional=True),
          output_filename=String('output_filename', min_length=1,
                                 optional=True),
          output_source=OUTPUT_SOURCE, output_type=OUTPUT_TYPE,
          points=TextNumber('points'),
          stdin=ViewableDBThing('stdin_id', File, optional=True),
          test_case=EditableDBThing('test_case_id', TestCase,
                                    source=MATCHDICT))
@test_case_verification
def test_case_update(request, name, args, expected, output_filename,
                     output_source, output_type, points, stdin, test_case):
    if not test_case.update(name=name, args=args, expected=expected,
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
        return http_conflict(request, message=('That name already exists for '
                                               'the project'))
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
          project_id=TextNumber('project_id', min_value=0))
def testable_create(request, name, make_target, executable, build_file_ids,
                    execution_file_ids, file_verifier_ids, project_id):
    project = Project.fetch_by_id(project_id)
    if not project:
        return http_bad_request(request, messages='Invalid project_id')
    if not project.can_edit(request.user):
        return HTTPForbidden()
    if make_target and not project.makefile:
        return http_bad_request(request, messages=('make_target cannot be '
                                                   'specified without a make '
                                                   'file'))

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
        return http_bad_request(request,
                                messages='Invalid {0}'.format(exc.message))

    testable = Testable(name=name, make_target=make_target,
                        executable=executable, project=project)
    map(testable.build_files.append, build_files)
    map(testable.execution_files.append, execution_files)
    map(testable.file_verifiers.append, file_verifiers)

    session = Session()
    session.add(testable)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('That name already exists for '
                                               'the project'))

    redir_location = request.route_path('project_edit',
                                        project_id=project_id)
    return http_created(request, redir_location=redir_location)


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
                                 TextNumber('', min_value=0), optional=True))
def testable_edit(request, name, make_target, executable, build_file_ids,
                  execution_file_ids, file_verifier_ids):
    testable_id = request.matchdict['testable_id']
    testable = Testable.fetch_by_id(testable_id)
    if not testable:
        return http_bad_request(request, messages='Invalid testable_id')
    if not testable.project.can_edit(request.user):
        return HTTPForbidden()
    if make_target and not testable.project.makefile:
        return http_bad_request(request, messages=('make_target cannot be '
                                                   'specified without a make '
                                                   'file'))

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
        return http_bad_request(request,
                                messages='Invalid {0}'.format(exc.message))

    if not testable.update(_ignore_order=True, name=name,
                           make_target=make_target,
                           executable=executable,
                           build_files=build_files,
                           execution_files=execution_files,
                           file_verifiers=file_verifiers):
        return http_ok(request, message='Nothing to change')

    session = Session()
    session.add(testable)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('That name already exists for '
                                               'the project'))
    return http_ok(request, message='Testable updated')


@view_config(route_name='testable_item', request_method='DELETE',
             permission='authenticated', renderer='json')
def testable_delete(request):
    testable = Testable.fetch_by_id(request.matchdict['testable_id'])
    if not testable:
        return http_bad_request(request, messages='Invalid testable_id')
    if not testable.project.can_edit(request.user):
        return HTTPForbidden()

    redir_location = request.route_path('project_edit',
                                        project_id=testable.project.id)
    request.session.flash('Deleted Testable {0}.'.format(testable.name))
    # Delete the file
    session = Session()
    session.delete(testable)
    transaction.commit()
    return http_ok(request, redir_location=redir_location)


@view_config(route_name='user_class_join', request_method='POST',
             permission='authenticated', renderer='json')
def user_class_join(request):
    class_name = request.matchdict['class_name']
    username = request.matchdict['username']
    if request.user.username != username:
        return http_bad_request(request, messages='Invalid user')
    klass = Class.fetch_by(name=class_name)
    if not klass:
        return http_bad_request(request, messages='Invalid class')
    request.user.classes.append(klass)
    session = Session()
    session.add(request.user)
    transaction.commit()
    redir_location = request.route_path('class_join_list',
                                        _query={'last_class': class_name})
    return http_created(request, redir_location=redir_location)


@view_config(route_name='user', renderer='json', request_method='PUT')
@validate(name=String('name', min_length=3),
          username=String('email', min_length=6, max_length=64),
          password=WhiteSpaceString('password', min_length=6),
          admin_for=List('admin_for', TextNumber('', min_value=0),
                         optional=True))
def user_create(request, name, username, password, admin_for):
    # get the classes we are requesting, and make sure
    # they are all valid
    asking_classes = []
    if admin_for:
        for class_id in admin_for:
            klass = Class.fetch_by_id(class_id)
            if klass is None:
                return http_bad_request(request, messages='Nonexistent class')
            asking_classes.append(klass)

    # make sure we can actually grant the permissions we
    # are requesting
    if asking_classes and not request.user.is_admin:
        can_add_permission_for = frozenset(request.user.admin_for)
        asking_permission_for = frozenset(asking_classes)
        if len(asking_permission_for - can_add_permission_for) > 0:
            return http_bad_request(
                request, messages=('Insufficient permissions to add '
                                   'permissions.'))

    session = Session()
    user = User(name=name, username=username, password=password,
                is_admin=False)
    user.admin_for.extend(asking_classes)
    session.add(user)
    try:
        transaction.commit()
    except IntegrityError:
        transaction.abort()
        return http_conflict(request, message=('User \'{0}\' already exists'
                                               .format(username)))
    redir_location = request.route_path('session',
                                        _query={'username': username})
    return http_created(request, redir_location=redir_location)


@view_config(route_name='user_new', renderer='templates/user_create.pt',
             request_method='GET')
@site_layout('nudibranch:templates/layout.pt')
def user_edit(request):
    can_add_admin_for = None
    if request.user:
        can_add_admin_for = request.user.classes_can_admin()

    return {'page_title': 'Create User',
            'admin_classes': can_add_admin_for}


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
    user = User.fetch_by(username=request.matchdict['username'])
    if not user:
        return HTTPNotFound()
    return {'page_title': 'User Page',
            'name': user.name,
            'classes_taking': user.classes,
            'classes_admining': user.classes_can_admin()}


@view_config(route_name='admin_utils', request_method='GET',
             permission='admin',
             renderer='templates/admin_utils.pt')
@site_layout('nudibranch:templates/layout.pt')
def admin_view(request):
    return {'page_title': 'Administrator Utilities'}


@view_config(route_name='class_admin_utils', request_method='GET',
             permission='authenticated',
             renderer='templates/class_admin_utils.pt')
@site_layout('nudibranch:templates/layout.pt')
def class_admin_view(request):
    if not request.user.is_admin_for_any_class():
        return HTTPForbidden()
    return {'page_title': 'Class Administrator Utilities'}
