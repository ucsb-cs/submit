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


def initialize_sql(engine):
    Session.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
