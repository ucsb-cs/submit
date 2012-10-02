import errno
import os
from pyramid_addons.helpers import load_settings
from sqla_mixins import BasicBase, UserMixin
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Table, Unicode, desc, engine_from_config)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.schema import UniqueConstraint
from zope.sqlalchemy import ZopeTransactionExtension

Base = declarative_base(cls=BasicBase)
Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


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


class Class(Base):
    name = Column(Unicode, nullable=False, unique=True)
    projects = relationship('Project', backref='klass')

    @staticmethod
    def fetch_by_id(class_id):
        session = Session()
        return session.query(Class).filter_by(id=class_id).first()

    @staticmethod
    def fetch_by_name(name):
        session = Session()
        return session.query(Class).filter_by(name=name).first()

    def __repr__(self):
        return 'Class(name={0})'.format(self.name)

    def __str__(self):
        return 'Class Name: {0}'.format(self.name)


class File(Base):
    lines = Column(Integer, nullable=False)
    sha1 = Column(Unicode, nullable=False, unique=True)
    size = Column(Integer, nullable=False)

    @staticmethod
    def fetch_by_sha1(sha1):
        session = Session()
        return session.query(File).filter_by(sha1=sha1).first()

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


class FileVerifier(Base):
    __table_args__ = (UniqueConstraint('filename', 'project_id'),)
    filename = Column(Unicode, nullable=False)
    min_size = Column(Integer, nullable=False)
    max_size = Column(Integer)
    min_lines = Column(Integer, nullable=False)
    max_lines = Column(Integer)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)

    def verify(self, data):
        msgs = []
        size = len(data)
        lines = data.count('\n')
        if size < self.min_size:
            msgs.append('file must be >= {0} bytes'.format(self.min_size))
        elif size > self.max_size:
            msgs.append('file must be <= {0} bytes'.format(self.max_size))
        if lines < self.min_lines:
            msgs.append('file must have >= {0} lines'.format(self.min_lines))
        elif lines > self.max_lines:
            msgs.append('file must have <= {0} lines'.format(self.max_lines))
        return msgs


class Project(Base):
    __table_args__ = (UniqueConstraint('name', 'class_id'),)
    name = Column(Unicode, nullable=False)
    class_id = Column(Integer, ForeignKey('class.id'), nullable=False)
    file_verifiers = relationship('FileVerifier', backref='project')

    @staticmethod
    def fetch_by_id(project_id):
        session = Session()
        return session.query(Project).filter_by(id=project_id).first()

    def verify_file(self, filename, data):
        for file_verifier in self.file_verifiers:
            if file_verifier.filename == filename:
                return file_verifier.verify(data)
        else:
            return '{0} is not a valid filename'.format(filename)


class User(UserMixin, Base):
    """The UserMixin provides the `username` and `password` attributes.
    `password` is a write-only attribute and can be verified using the
    `verify_password` function."""
    name = Column(Unicode, nullable=False)
    email = Column(Unicode, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    classes = relationship(Class, secondary=user_to_class, backref="users")
    files = relationship(File, secondary=user_to_file, backref="users")

    @staticmethod
    def fetch_by_id(user_id):
        session = Session()
        return session.query(User).filter_by(id=user_id).first()

    @staticmethod
    def fetch_by_name(username):
        session = Session()
        return session.query(User).filter_by(username=username).first()

    @staticmethod
    def login(username, password):
        """Return the user if successful, None otherwise"""
        retval = None
        session = Session()
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
    admin = User(email='root@localhost', name='Administrator',
                 username='admin', password='password', is_admin=True)
    Session.add(admin)
    try:
        transaction.commit()
        print('Admin user created')
    except IntegrityError:
        transaction.abort()
