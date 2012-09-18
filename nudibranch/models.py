from pyramid_addons.helpers import load_settings
from sqla_mixins import BasicBase, UserMixin
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Table, Unicode, desc, engine_from_config)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

Base = declarative_base(cls=BasicBase)
Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


user_to_class = Table('association', Base.metadata,
                      Column('user_id', Integer, ForeignKey('user.id')),
                      Column('class_id', Integer, ForeignKey('class.id')))


class User(UserMixin, Base):
    """The UserMixin provides the `username` and `password` attributes.
    `password` is a write-only attribute and can be verified using the
    `verify_password` function."""
    name = Column(Unicode, nullable=False)
    email = Column(Unicode, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
#classes = relationship('Classes', secondary=user_to_class, backref="users")

    @staticmethod
    def fetch_user_by_id(user_id):
        session = Session()
        user = session.query(User).filter_by(id=user_id).first()
        return user

    @staticmethod
    def fetch_user_by_name(username):
        session = Session()
        user = session.query(User).filter_by(username=username).first()
        return user

    @staticmethod
    def login(username, password):
        """Return the user if successful, None otherwise"""
        retval = None
        session = Session()
        try:
            user = User.fetch_user_by_name(username)
            if user and user.verify_password(password):
                retval = user
        except OperationalError:
            pass
        return retval

    def __str__(self):
        return 'Name: {0} Username: {1} Email: {2}'.format(self.name,
                                                           self.username,
                                                           self.email)

    def __repr__(self):
        return 'User(email="{0}", name="{1}", username="{2}")'.format(
            self.email, self.name, self.username)


class Class(Base):
    class_name = Column(Unicode)

    @staticmethod
    def fetch_class(class_name):
        session = Session()
        course = session.query(Class).filter_by(class_name=class_name).first()
        return course

    def __str__(self):
        return 'Course Name: {0}'.format(self.class_name)


def initialize_sql(engine):
    Session.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)


def reset_database(engine):
    Base.metadata.drop_all(engine)
