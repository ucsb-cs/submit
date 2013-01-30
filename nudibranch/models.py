from __future__ import unicode_literals
import errno
import os
import re
import sys
from hashlib import sha1
from sqla_mixins import BasicBase, UserMixin
from sqlalchemy import (Boolean, Column, DateTime, Enum, ForeignKey, Integer,
                        PickleType, String, Table, Unicode, UnicodeText, func)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.schema import UniqueConstraint
from zope.sqlalchemy import ZopeTransactionExtension

if sys.version_info < (3, 0):
    builtins = __import__('__builtin__')
else:
    import builtins

Base = declarative_base()
Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
# Make Session available to sqla_mixins
builtins._sqla_mixins_session = Session


testable_to_build_file = Table(
    'testable_to_build_file', Base.metadata,
    Column('testable_id', Integer, ForeignKey('testable.id'), nullable=False),
    Column('build_file_id', Integer, ForeignKey('buildfile.id'),
           nullable=False))

testable_to_execution_file = Table(
    'testable_to_execution_file', Base.metadata,
    Column('testable_id', Integer, ForeignKey('testable.id'), nullable=False),
    Column('execution_file_id', Integer, ForeignKey('executionfile.id'),
           nullable=False))

testable_to_file_verifier = Table(
    'testable_to_file_verifier', Base.metadata,
    Column('testable_id', Integer, ForeignKey('testable.id'), nullable=False),
    Column('file_verifier_id', Integer, ForeignKey('fileverifier.id'),
           nullable=False))

user_to_class = Table(
    'user_to_class', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id'), nullable=False),
    Column('class_id', Integer, ForeignKey('class.id'), nullable=False))

user_to_file = Table(
    'user_to_file', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id'), nullable=False),
    Column('file_id', Integer, ForeignKey('file.id'), nullable=False))

# which classes a user is an admin for
user_to_class_admin = Table('user_to_class_admin', Base.metadata,
                            Column('user_id', Integer, ForeignKey('user.id'),
                                   nullable=False),
                            Column('class_id', Integer, ForeignKey('class.id'),
                                   nullable=False))


class BuildFile(BasicBase, Base):
    __table_args__ = (UniqueConstraint('filename', 'project_id'),)
    file = relationship('File', backref='build_files')
    file_id = Column(Integer, ForeignKey('file.id'), nullable=False)
    filename = Column(Unicode, nullable=False)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)


class Class(BasicBase, Base):
    name = Column(Unicode, nullable=False, unique=True)
    projects = relationship('Project', backref='klass',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return 'Class(name={0})'.format(self.name)

    def __str__(self):
        return 'Class Name: {0}'.format(self.name)

    def __cmp__(self, other):
        return cmp(self.name, other.name)

    @staticmethod
    def all_classes_by_name():
        return Session().query(Class).order_by(Class.name).all()


class ExecutionFile(BasicBase, Base):
    __table_args__ = (UniqueConstraint('filename', 'project_id'),)
    file = relationship('File', backref='execution_files')
    file_id = Column(Integer, ForeignKey('file.id'), nullable=False)
    filename = Column(Unicode, nullable=False)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)


class File(BasicBase, Base):
    lines = Column(Integer, nullable=False)
    sha1 = Column(String, nullable=False, unique=True)
    size = Column(Integer, nullable=False)

    @staticmethod
    def fetch_or_create(data, base_path, sha1sum=None):
        if not sha1sum:
            sha1sum = sha1(data).hexdigest()
        file = File.fetch_by(sha1=sha1sum)
        if not file:
            file = File(base_path=base_path, data=data, sha1=sha1sum)
            session = Session()
            session.add(file)
            session.flush()  # Cannot commit the transaction here
        return file

    @staticmethod
    def file_path(base_path, sha1sum):
        first = sha1sum[:2]
        second = sha1sum[2:4]
        return os.path.join(base_path, first, second, sha1sum[4:])

    def __init__(self, base_path, data, sha1):
        self.lines = 0
        for byte in data:
            if byte == '\n':
                self.lines += 1
        self.size = len(data)
        self.sha1 = sha1
        # save file
        path = File.file_path(base_path, sha1)
        try:
            os.makedirs(os.path.dirname(path))
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise
        with open(path, 'wb') as fp:
            fp.write(data)


class FileVerifier(BasicBase, Base):
    __table_args__ = (UniqueConstraint('filename', 'project_id'),)
    filename = Column(Unicode, nullable=False)
    min_size = Column(Integer, nullable=False)
    max_size = Column(Integer)
    min_lines = Column(Integer, nullable=False)
    max_lines = Column(Integer)
    optional = Column(Boolean, default=False, nullable=False)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)
    warning_regex = Column(Unicode)

    def __cmp__(self, other):
        return cmp(self.filename, other.filename)

    def verify(self, base_path, file):
        errors = []
        if file.size < self.min_size:
            errors.append('must be >= {0} bytes'.format(self.min_size))
        elif self.max_size and file.size > self.max_size:
            errors.append('must be <= {0} bytes'.format(self.max_size))
        if file.lines < self.min_lines:
            errors.append('must have >= {0} lines'.format(self.min_lines))
        elif self.max_lines and file.lines > self.max_lines:
            errors.append('must have <= {0} lines'.format(self.max_lines))

        if not self.warning_regex:
            return errors, None

        regex = re.compile(self.warning_regex)
        warnings = []
        for i, line in enumerate(open(File.file_path(base_path, file.sha1))):
            for match in regex.findall(line):
                warnings.append({'lineno': i + 1, 'token': match})
        return errors, warnings


class VerificationResults(object):
    def __init__(self):
        self._errors_by_filename = {}
        self._warnings_by_filename = {}
        self._extra_filenames = []
        self._missing_to_testable_ids = {}

    def set_errors_for_filename(self, errors, filename):
        self._errors_by_filename[filename] = errors

    def set_warnings_for_filename(self, warnings, filename):
        self._warnings_by_filename[filename] = warnings

    def set_extra_filenames(self, filenames):
        self._extra_filenames = filenames

    def add_testable_id_for_missing_files(self, testable_id, missing_files):
        self._missing_to_testable_ids.setdefault(
            missing_files, set()).add(testable_id)


class Project(BasicBase, Base):
    __table_args__ = (UniqueConstraint('name', 'class_id'),)
    build_files = relationship(BuildFile, backref='project',
                               cascade='all, delete-orphan')
    class_id = Column(Integer, ForeignKey('class.id'), nullable=False)
    execution_files = relationship(ExecutionFile, backref='project',
                                   cascade='all, delete-orphan')
    file_verifiers = relationship('FileVerifier', backref='project',
                                  cascade='all, delete-orphan')
    makefile = relationship(File)
    makefile_id = Column(Integer, ForeignKey('file.id'), nullable=True)
    name = Column(Unicode, nullable=False)
    submissions = relationship('Submission', backref='project',
                               cascade='all, delete-orphan')
    testables = relationship('Testable', backref='project',
                             cascade='all, delete-orphan')

    def verify_submission(self, base_path, submission):
        """Return list of testables that can be built.

        Store into submission.results a dictionary with possible keys:
          :key errors: a mapping of filenames to reason(s) why that file is
              not valid
          :key warnings: a mapping of filesnames to lines that may contain
              invalid content (from warning_regex)
          :key extra: a list of filenames that aren't needed
          :key map: a mapping of set of filenames that are invalid to a list of
              testgroups that won't build because of those files

        """

        results = VerificationResults()
        valid_files = set()
        file_mapping = dict([(x.filename, x) for x in submission.files])

        # Create a list of in-use file verifiers
        file_verifiers = [fv for testable in self.testables
                          for fv in testable.file_verifiers]

        for fv in file_verifiers:
            name = fv.filename
            if name in file_mapping:
                errors, warnings = fv.verify(base_path,
                                             file_mapping[name].file)
                if errors:
                    results.set_errors_for_filename(errors, name)
                else:
                    valid_files.add(name)
                if warnings:
                    results.set_warnings_for_filename(warnings, name)
                del file_mapping[name]
            elif not fv.optional:
                results.set_errors_for_filename(['file missing'], name)
        if file_mapping:
            results.set_extra_filenames(list(file_mapping.keys()))

        # Determine valid testables
        retval = []
        for testable in self.testables:
            missing = frozenset(set(x.filename for x in testable.file_verifiers
                                    if not x.optional) - valid_files)
            if missing:
                results.add_testable_id_for_missing_files(
                    testable.id, missing)
            elif testable.file_verifiers:
                retval.append(testable)

        submission.verification_results = results
        submission.verified_at = func.now()
        return retval

    def _first_with_filter(self, user, pred, reverse=False):
        lst = sorted([u for u in self.klass.users
                      if pred(u)],
                     reverse=reverse)
        return lst[0] if lst else None

    def next_user(self, user):
        '''Returns the next user (determined by name), or None if this
        is the last user'''
        # TODO: how are you supposed to do a query across an association
        # table?
        return self._first_with_filter(user,
                                       lambda u: u.name > user.name)

    def prev_user(self, user):
        return self._first_with_filter(user,
                                       lambda u: u.name < user.name,
                                       reverse=True)


class Submission(BasicBase, Base):
    files = relationship('SubmissionToFile', backref='submissions')
    made_at = Column(DateTime(timezone=True), index=True)
    make_results = Column(UnicodeText)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)
    test_case_results = relationship('TestCaseResult', backref='submission')
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    verification_results = Column(PickleType)
    verified_at = Column(DateTime(timezone=True), index=True)

    @staticmethod
    def get_or_empty(item, if_not_none):
        return if_not_none(item) if item is not None else {}

    def had_verification_errors(self):
        return len(self.file_errors_from_verification())

    def file_warnings(self):
        '''Returns a mapping of filenames to warnings about said files'''
        return self.get_or_empty(self.verification_results,
                                 lambda vr: vr._warnings_by_filename)

    def file_errors_from_verification(self):
        return self.get_or_empty(self.verification_results,
                                 lambda vr: vr._errors_by_filename)

    def file_errors_from_build(self):
        '''Returns a mapping of filenames to errors about said files'''
        pairs = [(file, ['Build failed (see make output)'])
                 for files in self.build_failed_files_to_test_cases().keys()
                 for file in files]
        return dict(pairs)

    def file_errors(self):
        from_verify = self.file_errors_from_verification()
        from_build = self.file_errors_from_build()
        return self.merge_dict(from_verify,
                               from_build,
                               lambda v1, v2: v1 + v2)

    def test_cases(self):
        project = Project.fetch_by_id(self.project_id)
        if project:
            return frozenset([test_case
                              for testable in project.testables
                              for test_case in testable.test_cases])
        else:
            # shouldn't be possible
            return frozenset()

    def tests_that_ran(self):
        test_cases = [TestCase.fetch_by_id(test_case_result.test_case_id)
                      for test_case_result in self.test_case_results]
        return frozenset([test_case for test_case in test_cases
                          if test_case is not None])

    def tests_that_did_not_run(self):
        return self.test_cases() - self.tests_that_ran()

    def build_failed_files_to_test_cases(self):
        """Return mapping of files to test cases for build issues."""
        retval = {}
        failed_cases = self.tests_that_did_not_run()
        for test_case in failed_cases:
            testable = Testable.fetch_by_id(test_case.testable_id)
            if testable:
                retval.setdefault(
                    frozenset(testable.needed_files()),
                    set()).add(test_case)
        return retval

    def had_build_errors(self):
        '''Returns None if the build isn't done yet, True if it did,
        and False if it didn't'''
        if self.made_at and self.make_results:
            # build completed
            return len(self.tests_that_did_not_run()) > 0
        else:
            return None

    @staticmethod
    def merge_dict(d1, d2, on_collision):
        retval = {}
        for key in d1.keys():
            if key in d2:
                retval[key] = on_collision(d1[key], d2[key])
            else:
                retval[key] = d1[key]
        for key in d2.keys():
            if key not in retval:
                retval[key] = d2[key]
        return retval

    def defective_files_to_test_cases(self):
        """Return mapping of sets of defective files to failed test cases.

        Return None if the verification hasn't occured yet.

        Defective" means that the file was missing, failed verification, or
        failed the build.

        """
        from_verify = self.missing_or_verification_files_to_test_cases()
        if not from_verify:
            return None
        from_build = self.build_failed_files_to_test_cases()
        return self.merge_dict(from_verify, from_build,
                               lambda v1, v2: v1.union(v2))

    def missing_or_verification_files_to_test_cases(self):
        """Return mapping of file(s) to test cases for issues.

        Returns None if verification hasn't taken place.

        """
        def testable_id_to_test_cases(testable_id):
            testable = Testable.fetch_by_id(testable_id)
            return testable.test_cases if testable else []

        def testable_ids_to_test_cases(testable_ids):
            return frozenset(test_case for tid in testable_ids
                             for test_case in testable_id_to_test_cases(tid))

        if self.verification_results:
            files_to_ids = self.verification_results._missing_to_testable_ids
            return dict(
                (files, testable_ids_to_test_cases(ids))
                for files, ids in files_to_ids.iteritems())
        else:
            return None

    @staticmethod
    def most_recent_submission(project_id, user_id):
        '''Given the project id and a user id, gets the most recent
        submission for the given user, or None if the user has no
        submissions'''
        submissions = Submission.sorted_submissions(
            Submission.query_by(user_id=user_id,
                                project_id=project_id).all(),
            reverse=True)
        if submissions:
            return submissions[0]

    @staticmethod
    def next_user_with_submissions_submission(user, project):
        '''Gets the first submission available for the next user,
        skipping any users who have no submissions.  Returns None if
        we are at the end.
        NOTE: as written, this will only deterministically work correctly
        with a non-SQLite backend'''
        while True:
            next_user = project.next_user(user)
            if not next_user:
                return None
            next_submission = (Submission
                               .query_by(project=project, user=next_user)
                               .order_by(Submission.created_at.desc()).first())
            if next_submission:
                return next_submission
            user = next_user

    @staticmethod
    def later_submission_for_user(earlier_sub):
        return next_in_sorted(
            earlier_sub,
            Submission.sorted_submissions_for_submission(earlier_sub))

    @staticmethod
    def earlier_submission_for_user(later_sub):
        '''Returns the next submission for the user behind the submission, or
        None if this is the last user's submission.  The submissions returned
        will be in order of the submission created_at time'''

        # the below code is if we have proper datetime support at the
        # database level (i.e. not SQLite)
        # return Session().query(Submission).\
        #     filter(Submission.project_id == later_sub.project_id,
        #            Submission.user_id == later_sub.user_id,
        #            Submission.created_at < later_sub.created_at).\
        #     order_by(Submission.created_at.desc()).\
        #     first()

        # the below code is needed for SQLite
        return prev_in_sorted(
            later_sub,
            Submission.sorted_submissions_for_submission(later_sub))

    @staticmethod
    def query_submissions_for_same(submission):
        '''Gets all submissions for the same project and user
        as the given submission'''
        return Submission.query_by(user=submission.user,
                                   project=submission.project)

    @staticmethod
    def sorted_submissions_for_submission(submission, reverse=False):
        return Submission.sorted_submissions(
            Submission.query_submissions_for_same(submission).all(),
            reverse)

    @staticmethod
    def sorted_submissions(submissions, reverse=False):
        return sorted(submissions,
                      key=lambda s: s.created_at,
                      reverse=reverse)

    def verify(self, base_path):
        return self.project.verify_submission(base_path, self)

    def update_makefile_results(self, data):
        self.made_at = func.now()
        self.make_results = data


class SubmissionToFile(Base):
    __tablename__ = 'submissiontofile'
    file = relationship(File, backref='submission_assocs')
    file_id = Column(Integer, ForeignKey('file.id'), nullable=False)
    filename = Column(Unicode, nullable=False, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submission.id'),
                           primary_key=True, nullable=False)

    @staticmethod
    def fetch_file_mapping_for_submission(submission_id):
        '''Given a submission id, it returns a mapping of filenames
        to File objects'''
        results = Session().query(SubmissionToFile).filter_by(
            submission_id=submission_id)
        return dict([(stf.filename, stf.file) for stf in results])


class TestCase(BasicBase, Base):
    __table_args__ = (UniqueConstraint('name', 'testable_id'),)
    args = Column(Unicode, nullable=False)
    expected = relationship(File, primaryjoin='File.id==TestCase.expected_id')
    expected_id = Column(Integer, ForeignKey('file.id'), nullable=False)
    name = Column(Unicode, nullable=False)
    points = Column(Integer, nullable=False)
    testable_id = Column(Integer, ForeignKey('testable.id'), nullable=False)
    stdin = relationship(File, primaryjoin='File.id==TestCase.stdin_id')
    stdin_id = Column(Integer, ForeignKey('file.id'), nullable=True)
    test_case_for = relationship('TestCaseResult', backref='test_case')

    def __cmp__(self, other):
        return cmp(self.name, other.name)

    def serialize(self):
        data = dict([(x, getattr(self, x)) for x in ('id', 'args')])
        if self.stdin:
            data['stdin'] = self.stdin.sha1
        else:
            data['stdin'] = None
        return data


class TestCaseResult(Base):
    """Stores information about a test case.

    The extra field stores the exit status when the status is `success`, and
    stores the signal number when the status is `signal`.
    """
    __tablename__ = 'testcaseresult'
    diff = relationship(File)
    diff_id = Column(Integer, ForeignKey('file.id'), nullable=True)
    status = Column(Enum('nonexistent_executable', 'signal',
                         'success', 'timed_out',
                         name='status', nullable=False))
    extra = Column(Integer)
    submission_id = Column(Integer, ForeignKey('submission.id'),
                           primary_key=True, nullable=False)
    test_case_id = Column(Integer, ForeignKey('testcase.id'),
                          primary_key=True, nullable=False)

    @classmethod
    def fetch_by_ids(cls, submission_id, test_case_id):
        session = Session()
        return session.query(cls).filter_by(
            submission_id=submission_id, test_case_id=test_case_id).first()

    def update(self, data):
        for attr, val in data.items():
            setattr(self, attr, val)
        self.created_at = func.now()


class Testable(BasicBase, Base):
    """Represents a set of properties for a single program to test."""
    __table_args__ = (UniqueConstraint('name', 'project_id'),)
    build_files = relationship(BuildFile, backref='testables',
                               secondary=testable_to_build_file)
    executable = Column(Unicode, nullable=False)
    execution_files = relationship(ExecutionFile, backref='testables',
                                   secondary=testable_to_execution_file)
    file_verifiers = relationship(FileVerifier, backref='testables',
                                  secondary=testable_to_file_verifier)
    make_target = Column(Unicode)  # When None, no make is required
    name = Column(Unicode, nullable=False)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)
    test_cases = relationship('TestCase', backref='testable',
                              cascade='all, delete-orphan')

    def needed_files(self):
        return sorted([fv.filename for fv in self.file_verifiers])


class User(UserMixin, BasicBase, Base):
    """The UserMixin provides the `username` and `password` attributes.
    `password` is a write-only attribute and can be verified using the
    `verify_password` function."""
    name = Column(Unicode, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    classes = relationship(Class, secondary=user_to_class, backref='users')
    files = relationship(File, secondary=user_to_file, backref='users')
    admin_for = relationship(Class, secondary=user_to_class_admin,
                             backref='admins')
    submissions = relationship('Submission', backref='user')

    @staticmethod
    def is_int(value):
        try:
            int(value)
            return True
        except ValueError:
            pass
        return False

    def classes_can_admin(self):
        '''Gets all the classes that this user can administrate.
        Returned in order by name'''
        if self.is_admin:
            return Class.all_classes_by_name()
        else:
            return sorted(self.admin_for)

    def is_admin_for_any_class(self):
        return len(self.admin_for) > 0

    def is_admin_for_class(self, cls):
        '''Takes either a class, a class name, or a class id.
        Note that the toplevel admin is considered viable.
        If we are given a string representation of a class id,
        it will try it as a class name first, then as a normal id'''
        if self.is_admin:
            return True
        if isinstance(cls, int):
            cls = Class.fetch_by(id=cls)
        elif isinstance(cls, basestring):
            orig = cls
            cls = Class.fetch_by(name=cls)
            if not cls and User.is_int(orig):
                cls = Class.fetch_by(id=orig)
        return cls and cls in self.admin_for

    @staticmethod
    def get_value(cls, value):
        '''Takes the class of the item that we want to
        query, along with a potential instance of that class.
        If the value is an instance of int or basestring, then
        we will treat it like an id for that instance.'''
        if isinstance(value, (basestring, int)):
            value = cls.fetch_by(id=value)
        return value if isinstance(value, cls) else None

    def is_admin_for_something(self, cls, value, chain):
        '''chain is called only on something that is an instance
        of type cls'''
        if self.is_admin:
            return True
        value = User.get_value(cls, value)
        return value and chain(value)

    def is_admin_for_project(self, project):
        '''Takes either a project or a project id.
        The project id may be a string representation of the id'''
        return self.is_admin_for_something(
            Project, project,
            lambda p: self.is_admin_for_class(p.class_id))

    def is_admin_for_file_verifier(self, file_verifier):
        '''Takes either a file verifier or a file verifier id.
        The file verifier id may be a string representation.'''
        return self.is_admin_for_something(
            FileVerifier, file_verifier,
            lambda f: self.is_admin_for_project(f.project))

    def is_admin_for_test_case(self, test_case):
        '''Takes either a test case or a test case id.
        The test case id may be a string representation.'''
        return self.is_admin_for_something(
            TestCase, test_case,
            lambda t: self.is_admin_for_project(t.testable.project_id))

    def is_admin_for_testable(self, testable):
        '''Takes either a testabe or a testable id.
        The testable id may be a string representation.'''
        return self.is_admin_for_something(
            Testable, testable,
            lambda t: self.is_admin_for_project(t.project_id))

    def is_admin_for_submission(self, submission):
        '''Takes either a submission or a submission id.
        The submission id may be a string representation.'''
        return self.is_admin_for_something(
            Submission, submission,
            lambda s: self.is_admin_for_project(s.project_id))

    @staticmethod
    def login(username, password):
        """Return the user if successful, None otherwise"""
        retval = None
        try:
            user = User.fetch_by(username=username)
            if user and user.verify_password(password):
                retval = user
        except OperationalError:
            pass
        return retval

    def __cmp__(self, other):
        return cmp(self.name, other.name)

    def __repr__(self):
        return 'User(username="{0}", name="{1}")'.format(self.username,
                                                         self.name)

    def __str__(self):
        admin_str = '(admin)' if self.is_admin else ''
        return 'Name: {0} Email: {1} {2}'.format(self.name, self.username,
                                                 admin_str)


def configure_sql(engine):
    """Configure session and metadata with the database engine."""
    Session.configure(bind=engine)
    Base.metadata.bind = engine


def create_schema(alembic_config_ini=None):
    """Create the database schema.

    :param alembic_config_ini: When provided, stamp with the current revision
    version.

    """
    Base.metadata.create_all()
    if alembic_config_ini:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(alembic_config_ini)
        command.stamp(alembic_cfg, 'head')


def populate_database():
    """Populate the database with some data useful for development."""
    import transaction

    if User.fetch_by(username='admin'):
        return

    # Admin user
    admin = User(name='Administrator', password='password',
                 username='admin', is_admin=True)
    # Class
    klass = Class(name='CS32')
    Session.add(klass)
    Session.flush()

    # Project
    project = Project(name='Project 1', class_id=klass.id)
    Session.add(project)
    Session.flush()

    # File verification
    fv = FileVerifier(filename='test.c', min_size=3, min_lines=1,
                      project_id=project.id)

    Session.add_all([admin, fv])
    try:
        transaction.commit()
        print('Admin user created')
    except IntegrityError:
        transaction.abort()


# Prevent circular import
from .helpers import next_in_sorted, prev_in_sorted
