from configparser import RawConfigParser
from datetime import datetime
from functools import wraps
from pyramid.events import NewRequest, subscriber
from pyramid.httpexceptions import (HTTPBadRequest, HTTPConflict, HTTPCreated,
                                    HTTPException, HTTPGone)
from pyramid.renderers import get_renderer
from pytz import timezone

TIMEZONE = 'US/Pacific'  # Move this into settings at some point


def complete_date(the_datetime):
    return (the_datetime.replace(tzinfo=pytz.utc)
            .astimezone(timezone(TIMEZONE)).strftime('%H:%M, %A %B %d, %Y'))


def http_bad_request(request, messages):
    request.response.status = HTTPBadRequest.code
    return {'error': 'Invalid request', 'messages': messages}


def http_conflict(request, message):
    request.response.status = HTTPConflict.code
    return {'message': message}


def http_created(request, redir_location, headers=None):
    request.response.status = HTTPCreated.code
    if headers:
        request.response.headerlist.extend(headers)
    return {'redir_location': redir_location}


def http_gone(request, redir_location, headers=None):
    request.response.status = HTTPGone.code
    if headers:
        request.response.headerlist.extend(headers)
    return {'redir_location': redir_location}


def load_settings(config_file):
    config = RawConfigParser()
    if not config.read(config_file):
        raise Exception('Not a valid config file: {0!r}'.format(config_file))
    if config.has_section('app:main_helper'):
        settings = dict(config.items('app:main_helper'))
    else:
        settings = dict(config.items('app:main'))
    return settings


def pretty_date(the_datetime):
    # Source modified from
    # http://stackoverflow.com/a/5164027/176978
    diff = datetime.utcnow() - the_datetime
    if diff.days > 7 or diff.days < 0:
        return the_datetime.strftime('%A %B %d, %Y')
    elif diff.days == 1:
        return '1 day ago'
    elif diff.days > 1:
        return '{0} days ago'.format(diff.days)
    elif diff.seconds <= 1:
        return 'just now'
    elif diff.seconds < 60:
        return '{0} seconds ago'.format(diff.seconds)
    elif diff.seconds < 120:
        return '1 minute ago'
    elif diff.seconds < 3600:
        return '{0} minutes ago'.format(diff.seconds / 60)
    elif diff.seconds < 7200:
        return '1 hour ago'
    else:
        return '{0} hours ago'.format(diff.seconds / 3600)


def site_layout(function):
    """A decorator that incorporates the site layout template.

    This should only be used on view functions that return dictionaries.
    """
    @wraps(function)
    def wrapped(request, **kwargs):
        info = function(request, **kwargs)
        if isinstance(info, HTTPException):
            return info  # HTTPException objects should be immediately returned
        renderer = get_renderer('templates/layout.pt')
        # Required parameters
        info['_LAYOUT'] = renderer.implementation().macros['layout']
        info['_S'] = request.static_path
        info['_R'] = request.route_path
        # Required parameters that can be overwritten
        info.setdefault('javascripts', None)
        info.setdefault('page_title', None)
        return info
    return wrapped
