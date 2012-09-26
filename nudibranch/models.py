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


user_to_class = Table('association', Base.metadata,
                      Column('user_id', Integer, ForeignKey('user.id'),
                             nullable=False),
                      Column('class_id', Integer, ForeignKey('class.id'),
                             nullable=False))


class Class(Base):
    name = Column(Unicode, nullable=False, unique=True)
    projects = relationship('Project', backref='klass')

    @staticmethod
    def fetch_by_id(class_id):
        session = Session()
        klass = session.query(Class).filter_by(id=class_id).first()
        return klass

    @staticmethod
    def fetch_by_name(name):
        session = Session()
        course = session.query(Class).filter_by(name=name).first()
        return course

    def __repr__(self):
        return 'Class(name={0})'.format(self.name)

    def __str__(self):
        return 'Class Name: {0}'.format(self.name)


class Project(Base):
    __table_args__ = (UniqueConstraint('name', 'class_id'),)
    name = Column(Unicode, nullable=False)
    class_id = Column(Integer, ForeignKey('class.id'), nullable=False)

    @staticmethod
    def fetch_by_id(project_id):
        session = Session()
        project = session.query(Project).filter_by(id=project_id).first()
        return project


class User(UserMixin, Base):
    """The UserMixin provides the `username` and `password` attributes.
    `password` is a write-only attribute and can be verified using the
    `verify_password` function."""
    name = Column(Unicode, nullable=False)
    email = Column(Unicode, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    classes = relationship(Class, secondary=user_to_class, backref="users")

    @staticmethod
    def fetch_by_id(user_id):
        session = Session()
        user = session.query(User).filter_by(id=user_id).first()
        return user

    @staticmethod
    def fetch_by_name(username):
        session = Session()
        user = session.query(User).filter_by(username=username).first()
        return user

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
