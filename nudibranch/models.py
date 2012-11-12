from __future__ import unicode_literals
import errno
import os
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


user_to_class = Table('user_to_class', Base.metadata,
                      Column('user_id', Integer, ForeignKey('user.id'),
                             nullable=False),
                      Column('class_id', Integer, ForeignKey('class.id'),
                             nullable=False))

user_to_file = Table('user_to_file', Base.metadata,
                     Column('user_id', Integer, ForeignKey('user.id'),
                            nullable=False),
                     Column('file_id', Integer, ForeignKey('file.id'),
                            nullable=False))


class Class(BasicBase, Base):
    name = Column(Unicode, nullable=False, unique=True)
    projects = relationship('Project', backref='klass')

    @staticmethod
    def fetch_by_name(name):
        session = Session()
        return session.query(Class).filter_by(name=name).first()

    def __repr__(self):
        return 'Class(name={0})'.format(self.name)

    def __str__(self):
        return 'Class Name: {0}'.format(self.name)


class File(BasicBase, Base):
    lines = Column(Integer, nullable=False)
    sha1 = Column(String, nullable=False, unique=True)
    size = Column(Integer, nullable=False)

    @staticmethod
    def fetch_by_sha1(sha1):
        session = Session()
        return session.query(File).filter_by(sha1=sha1).first()

    @staticmethod
    def fetch_or_create(data, base_path, sha1sum=None):
        if not sha1sum:
            sha1sum = sha1(data).hexdigest()
        file = File.fetch_by_sha1(sha1sum)
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
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)

    def verify(self, file):
        msgs = []
        if file.size < self.min_size:
            msgs.append('must be >= {0} bytes'.format(self.min_size))
        elif self.max_size and file.size > self.max_size:
            msgs.append('must be <= {0} bytes'.format(self.max_size))
        if file.lines < self.min_lines:
            msgs.append('must have >= {0} lines'.format(self.min_lines))
        elif self.max_lines and file.lines > self.max_lines:
            msgs.append('must have <= {0} lines'.format(self.max_lines))
        if msgs:
            return False, msgs
        else:
            return True, None


class Project(BasicBase, Base):
    __table_args__ = (UniqueConstraint('name', 'class_id'),)
    name = Column(Unicode, nullable=False)
    class_id = Column(Integer, ForeignKey('class.id'), nullable=False)
    file_verifiers = relationship('FileVerifier', backref='project')
    submissions = relationship('Submission', backref='project')
    test_cases = relationship('TestCase', backref='project')
    makefile = relationship(File)
    makefile_id = Column(Integer, ForeignKey('file.id'))

    def verify_submission(self, submission):
        results = {'missing': [], 'passed': [], 'failed': []}
        file_mapping = dict([(x.filename, x) for x in submission.files])
        valid = True
        for fv in self.file_verifiers:
            name = fv.filename
            if name in file_mapping:
                passed, messages = fv.verify(file_mapping[name].file)
                valid &= passed
                if passed:
                    results['passed'].append(name)
                else:
                    results['failed'].append((name, messages))
                del file_mapping[name]
            else:
                valid = False
                results['missing'].append(name)
        results['extra'] = list(file_mapping.keys())
        submission.verification_results = results
        submission.verified_at = func.now()
        return valid


class Submission(BasicBase, Base):
    files = relationship('SubmissionToFile', backref='submissions')
    made_at = Column(DateTime, index=True)
    make_results = Column(UnicodeText)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)
    test_case_results = relationship('TestCaseResult', backref='submission')
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    verification_results = Column(PickleType)
    verified_at = Column(DateTime, index=True)

    @staticmethod
    def fetch_by_user_project(user_id, project_id):
        return Session().query(Submission).filter_by(
            user_id=user_id, project_id=project_id)

    def verify(self):
        return self.project.verify_submission(self)

    def update_makefile_results(self, data):
        self.made_at = func.now()
        self.make_results = data


class SubmissionToFile(Base):
    __tablename__ = 'submissiontofile'
    file = relationship(File, backref='submission_assocs')
    file_id = Column(Integer, ForeignKey('file.id'), primary_key=True)
    filename = Column(Unicode, nullable=False)
    submission_id = Column(Integer, ForeignKey('submission.id'),
                           primary_key=True)


class TestCase(BasicBase, Base):
    __table_args__ = (UniqueConstraint('name', 'project_id'),)
    args = Column(Unicode, nullable=False)
    expected = relationship(File, primaryjoin='File.id==TestCase.expected_id')
    expected_id = Column(Integer, ForeignKey('file.id'))
    name = Column(Unicode, nullable=False)
    points = Column(Integer, nullable=False)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)
    stdin = relationship(File, primaryjoin='File.id==TestCase.stdin_id')
    stdin_id = Column(Integer, ForeignKey('file.id'))
    test_case_for = relationship('TestCaseResult', backref='test_case')

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
    diff_id = Column(Integer, ForeignKey('file.id'))
    status = Enum('nonexistent_executable', 'signal', 'success', 'timed_out',
                  nullable=False)
    extra = Column(Integer)
    submission_id = Column(Integer, ForeignKey('submission.id'),
                           primary_key=True)
    test_case_id = Column(Integer, ForeignKey('testcase.id'),
                          primary_key=True)

    @classmethod
    def fetch_by_ids(cls, submission_id, test_case_id):
        session = Session()
        return session.query(cls).filter_by(
            submission_id=submission_id, test_case_id=test_case_id).first()

    def update(self, data):
        for attr, val in data.items():
            setattr(self, attr, val)
        self.created_at = func.now()


class User(UserMixin, BasicBase, Base):
    """The UserMixin provides the `username` and `password` attributes.
    `password` is a write-only attribute and can be verified using the
    `verify_password` function."""
    name = Column(Unicode, nullable=False)
    email = Column(Unicode, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    classes = relationship(Class, secondary=user_to_class, backref='users')
    files = relationship(File, secondary=user_to_file, backref='users')
    submissions = relationship('Submission', backref='user')

    @staticmethod
    def fetch_by_name(username):
        session = Session()
        return session.query(User).filter_by(username=username).first()

    @staticmethod
    def login(username, password):
        """Return the user if successful, None otherwise"""
        retval = None
        try:
            user = User.fetch_by_name(username)
            if user and user.verify_password(password):
                retval = user
        except OperationalError:
            pass
        return retval

    def __repr__(self):
        return 'User(email="{0}", name="{1}", username="{2}")'.format(
            self.email, self.name, self.username)

    def __str__(self):
        admin_str = '(admin)' if self.is_admin else ''
        return 'Name: {0} Username: {1} Email: {2} {3}'.format(self.name,
                                                               self.username,
                                                               self.email,
                                                               admin_str)


def initialize_sql(engine, populate=False):
    Session.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    if populate:
        populate_database()


def populate_database():
    import transaction

    if User.fetch_by_name('admin'):
        return

    # Admin user
    admin = User(email='root@localhost', name='Administrator',
                 username='admin', password='password', is_admin=True)
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
