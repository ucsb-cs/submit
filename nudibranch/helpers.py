import json
import pickle
import pika
import transaction
from pyramid_addons.helpers import (http_bad_request, http_conflict,
                                    http_created, http_forbidden, http_ok)
from pyramid_addons.validation import (SOURCE_MATCHDICT, TextNumber,
                                       ValidateAbort, Validator)
from pyramid.httpexceptions import HTTPForbidden, HTTPNotFound
from sqlalchemy.exc import IntegrityError
from tempfile import NamedTemporaryFile
from zipfile import ZipFile
from .diff_unit import Diff, DiffWithMetadata, DiffExtraInfo
from .exceptions import InvalidId
from .models import (BuildFile, File, FileVerifier, Session, Submission,
                     SubmissionToFile)


class DummyTemplateAttr(object):
    def __init__(self, default=None):
        self.default = default

    def __getattr__(self, attr):
        return self.default


class DBThing(Validator):

    """A validator that converts a primary key into the database object."""

    def __init__(self, param, cls, fetch_by=None, validator=None,
                 **kwargs):
        super(DBThing, self).__init__(param, **kwargs)
        self.cls = cls
        self.fetch_by = fetch_by
        self.id_validator = validator if validator else TextNumber(param,
                                                                   min_value=0)

    def run(self, value, errors, request):
        """Return the object if valid and available, otherwise None."""
        self.id_validator(value, errors, request)
        if errors:
            return None
        if self.fetch_by:
            thing = self.cls.fetch_by(**{self.fetch_by: value})
        else:
            thing = self.cls.fetch_by_id(value)
        if not thing and self.source == SOURCE_MATCHDICT:
            # If part of the URL we should have a not-found error
            raise HTTPNotFound()
        elif not thing:
            self.add_error(errors, 'Invalid {0}'
                           .format(self.cls.__name__))
        return thing


class EditableDBThing(DBThing):

    """An extension of DBThing that also checks for edit access.

    Usage of this validator assumes the Thing class has a `can_edit` method
    that takes as a sole argument a User object.

    """

    def run(self, value, errors, request):
        """Return thing, but abort validation if request.user cannot edit."""
        thing = super(EditableDBThing, self).run(value, errors, request)
        if errors:
            return None
        if not thing.can_edit(request.user):
            if self.source == SOURCE_MATCHDICT:
                # If part of the URL don't provide any extra information
                raise HTTPForbidden()
            message = 'Insufficient permissions for {0}'.format(self.param)
            raise ValidateAbort(http_forbidden(request, messages=message))
        return thing


class ViewableDBThing(DBThing):

    """An extension of DBThing that also checks for view access.

    Usage of this validator assumes the Thing class has a `can_view` method
    that takes as a sole argument a User object.

    """

    def run(self, value, errors, request):
        """Return thing, but abort validation if request.user cannot view."""
        thing = super(ViewableDBThing, self).run(value, errors, request)
        if errors:
            return None
        if not thing.can_view(request.user):
            if self.source == SOURCE_MATCHDICT:
                # If part of the URL don't provide any extra information
                raise HTTPForbidden()
            message = 'Insufficient permissions for {0}'.format(self.param)
            raise ValidateAbort(http_forbidden(request, messages=message))
        return thing


class ZipSubmission(object):
    """Puts a submission into a zip file.

    This packages up the following:
    -Makefile to build the project
    -User-submitted code that can be build with said makefile
    -Test cases, along with any stdin needed to run said test cases

    """
    def __init__(self, submission, request):
        self.submission = submission
        self.request = request
        self.dirname = '{0}_{1}'.format(submission.user.username,
                                        submission.id)
        self.backing_file = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, tpe, value, traceback):
        self.close()

    def _add_makefile(self):
        self.write(self.file_path(self.submission.project.makefile),
                   'Makefile')

    def _add_user_code(self):
        filemapping = SubmissionToFile.fetch_file_mapping_for_submission(
            self.submission.id)
        for filename, db_file in filemapping.iteritems():
            self.write(self.file_path(db_file), filename)

    def actual_filename(self):
        return self.backing_file.name

    def close(self):
        self.backing_file.close()
        self.backing_file = None

    def open(self):
        self.backing_file = NamedTemporaryFile()
        try:
            self.zip = ZipFile(self.backing_file, 'w')
            self._add_makefile()
            self._add_user_code()
        finally:
            self.zip.close()

    def file_path(self, file_):
        return File.file_path(self.request.registry.settings['file_directory'],
                              file_.sha1)

    def pretty_filename(self):
        return '{0}.zip'.format(self.dirname)

    def write(self, backing_file, archive_filename):
        '''Writes the given file to the archive with the given name.
        Puts everything in the same directory as specified by
        get_dirname_from_submission'''
        self.zip.write(backing_file,
                       "{0}/{1}".format(self.dirname, archive_filename))


def fetch_request_ids(item_ids, cls, attr_name, verification_list=None):
    """Return a list of cls instances for all the ids provided in item_ids.

    :param item_ids: The list of ids to fetch objects for
    :param cls: The class to fetch the ids from
    :param attr_name: The name of the attribute for exception purposes
    :param verification_list: If provided, a list of acceptable instances

    Raise InvalidId exception using attr_name if any do not
        exist, or are not present in the verification_list.

    """
    if not item_ids:
        return []
    items = []
    for item_id in item_ids:
        item = cls.fetch_by_id(item_id)
        if not item or (verification_list is not None and
                        item not in verification_list):
            raise InvalidId(attr_name)
        items.append(item)
    return items


def file_verifier_verification(function):
    def wrapped(request, min_size, max_size, min_lines, max_lines,
                *args, **kwargs):
        msgs = []
        if max_size is not None and max_size < min_size:
            msgs.append('min_size cannot be > max_size')
        if max_lines is not None and max_lines < min_lines:
            msgs.append('min_lines cannot be > max_lines')
        if min_size < min_lines:
            msgs.append('min_lines cannot be > min_size')
        if max_size is not None and max_lines is not None \
                and max_size < max_lines:
            msgs.append('max_lines cannot be > max_size')
        if msgs:
            return http_bad_request(request, messages=msgs)
        return function(request, *args, min_size=min_size, max_size=max_size,
                        min_lines=min_lines, max_lines=max_lines, **kwargs)
    return wrapped


def format_points(points):
    return "({0} {1})".format(
        points,
        "point" if points == 1 else "points")


def get_queue_func(request):
    """Establish the connection to rabbitmq."""
    def cleanup(request):
        conn.close()

    def queue_func(**kwargs):
        return conn.channel().basic_publish(
            exchange='', body=json.dumps(kwargs), routing_key=queue,
            properties=pika.BasicProperties(delivery_mode=2))
    server = request.registry.settings['queue_server']
    queue = request.registry.settings['queue_verification']
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=server))
    request.add_finished_callback(cleanup)
    return queue_func


def get_submission_stats(cls, project):
    """Return a dictionary of items containing submission stats.

    :key count: The total number of submissions
    :key unique: The total number of unique students submitting
    :key by_hour: A list containing the count and unique submissions by hour
    :key start: The datetime of the first submission
    :key end: The datetime of the most recent submission

    """
    count = 0
    unique = set()
    start = cur_date = None
    by_hour = []
    cur = None
    for submission in cls.query_by(project=project).order_by('created_at'):
        if submission.created_at.hour != cur_date:
            cur_date = submission.created_at.hour
            cur = {'count': 0, 'unique': set()}
            by_hour.append(cur)
        if not start:
            start = submission.created_at
        count += 1
        unique.add(submission.user_id)
        cur['count'] += 1
        cur['unique'].add(submission.user_id)
    return {'count': count, 'unique': len(unique), 'start': start,
            'end': submission.created_at, 'by_hour': by_hour}


def prev_next_submission(submission):
    """Return adjacent sumbission objects for the given submission."""
    return (Submission.earlier_submission_for_user(submission),
            Submission.later_submission_for_user(submission))


def prev_next_user(project, user):
    """Return adjacent user objects or None for the given project and user.

    The previous and next user objects are relative to sort order of the
    project's users with respect to the passed in user.

    """
    # TODO: Profile and optimize this query if necessary
    users = sorted(project.class_.users)
    try:
        index = users.index(user)
    except ValueError:
        return None, None
    prev_user = users[index - 1] if index > 0 else None
    next_user = users[index + 1] if index + 1 < len(users) else None
    return prev_user, next_user


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


def readlines(path):
    with open(path, 'r') as fh:
        return fh.read().splitlines()


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


def to_full_diff(request, test_case_result):
    """Return a completed DiffWithMetadata object."""
    try:
        diff_file = File.file_path(request.registry.settings['file_directory'],
                                   test_case_result.diff.sha1)
        diff = pickle.load(open(diff_file))
    except (AttributeError, EOFError):
        diff = Diff(['submit system mismatch -- requeue submission\n'], [])
    test_case = test_case_result.test_case
    return DiffWithMetadata(diff, test_case.id, test_case.testable.name,
                            test_case.name, test_case.points,
                            DiffExtraInfo(test_case_result.status,
                                          test_case_result.extra))
