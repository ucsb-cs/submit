from configparser import RawConfigParser
from datetime import datetime
from functools import wraps
from pyramid.events import NewRequest, subscriber
from pyramid.httpexceptions import HTTPException
from pyramid.renderers import get_renderer
from pytz import timezone

TIMEZONE = 'US/Pacific'  # Move this into settings at some point


def _app_url(request):
    if 'app_url' in request.registry.settings:
        return request.registry.settings['app_url']
    else:
        return request.application_url


@subscriber(NewRequest)
def app_url(event):
    event.request.set_property(_app_url, 'app_url', reify=True)


def complete_date(the_datetime):
    return (the_datetime.replace(tzinfo=pytz.utc)
            .astimezone(timezone(TIMEZONE)).strftime('%H:%M, %A %B %d, %Y'))


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
        info['_S'] = lambda x: static_path(request, x)
        info['_R'] = lambda *args, **kw: route_path(request, *args, **kw)
        # Required parameters that can be overwritten
        info.setdefault('javascripts', None)
        info.setdefault('page_title', None)
        return info
    return wrapped


def static_path(request, *args, **kwargs):
    full_path = request.static_url(*args, _app_url=request.app_url, **kwargs)
    return url_path(full_path)


def url_path(full_path):
    return '/' + full_path.split('/', 3)[-1]


def route_path(request, *args, **kwargs):
    full_path = request.route_url(*args, _app_url=request.app_url, **kwargs)
    return url_path(full_path)
