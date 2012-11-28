#!/user/bin/env python

# Demonstrates the datetime issue on SQLite
from sqlalchemy import Column, DateTime, Integer, create_engine, func
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm.session import sessionmaker
from time import sleep
import sqlite3

Base = declarative_base()


class Entry(Base):
    id = Column(Integer, primary_key=True)
    some_time = Column(DateTime,
                       default=func.now(),
                       index=True, nullable=False)

    @declared_attr
    def __tablename__(cls):
        """The table name will be the lowercase of the class name."""
        return cls.__name__.lower()


args = {'detect_types': sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES}
engine = create_engine('sqlite://',
                       connect_args=args,
                       native_datetime=True)
engine.echo = True
Base.metadata.bind = engine
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

entry1 = Entry(id=3)
session.add(entry1)
session.flush()
sleep(2)

entry2 = Entry(id=2)
session.add(entry2)
session.flush()
sleep(2)

entry3 = Entry(id=1)
session.add(entry3)
session.flush()

q = session.query(Entry).\
    filter(Entry.some_time < entry3.some_time).\
    order_by(Entry.some_time.desc()).\
    first()

# the id printed illustrates both that the order_by
# and filter constraints were completely ignored
print '{0}, "{1}"'.format(q.id, q.some_time)
