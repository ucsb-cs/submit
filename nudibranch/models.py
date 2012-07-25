from sqla_mixins import BasicBase, UserMixin
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Unicode, desc, engine_from_config)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
from .helpers import load_settings

Base = declarative_base(cls=BasicBase)
Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


class User(UserMixin, Base):
    """The UserMixin provides the `username` and `password` attributes.
    `password` is a write-only attribute and can be verified using the
    `verify_password` function."""
    name = Column(Unicode, nullable=False)
    email = Column(Unicode, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    @staticmethod
    def fetch_user(uname):
        session = Session()
        user = session.query(User).filter_by(username=uname).first()
        return user

    def __str__(self):
        return 'Name: {0} Username: {1} Email: {2}'.format(self.name,
                                                           self.username,
                                                           self.email)


class Class(Base):
    class_name = Column(Unicode)

    @staticmethod
    def fetch_class(class_name):
        session = Session()
        course = session.query(Class
                               ).filter_by(class_name=class_name).first()
        return course

    def __str__(self):
        return 'Course Name: {0}'.format(self.class_name)


def initialize_sql(engine):
    Session.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)


def reset_database(engine):
    Base.metadata.drop_all(engine)
