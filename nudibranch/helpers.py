import json
import pika
import xml.sax.saxutils
from pyramid_addons.helpers import http_forbidden
from pyramid_addons.validation import (SOURCE_MATCHDICT, TextNumber,
                                       ValidateAbort, Validator)
from pyramid.httpexceptions import HTTPForbidden, HTTPNotFound
from .exceptions import InvalidId


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


def readlines(path):
    with open(path, 'r') as fh:
        return fh.read().splitlines()


def escape(string):
    return xml.sax.saxutils.escape(string, {'"': "&quot;",
                                            "'": "&apos;"})


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


def offset_from_sorted(item, lst, offset):
    '''Takes an item to look for, a sorted list, and an offset.
    If the item is in the list and the offset is valid, then it
    will return the item at that offset.  Returns None if the
    offset is out of bounds and IndexError if the given item isn't
    found.'''
    index = lst.index(item) + offset
    if index >= 0 and index < len(lst):
        return lst[index]


def next_in_sorted(item, lst):
    '''Returns the next item in the given (assumed sorted) list,
    or None if it is already the last item.  Throws an IndexError if
    it doesn't exist at all'''
    return offset_from_sorted(item, lst, 1)


def prev_in_sorted(item, lst):
    return offset_from_sorted(item, lst, -1)
