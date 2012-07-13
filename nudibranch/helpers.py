from functools import wraps
from pyramid.events import NewRequest, subscriber
from pyramid.renderers import get_renderer


def _app_url(request):
    if 'app_url' in request.registry.settings:
        return request.registry.settings['app_url']
    else:
        return request.application_url


@subscriber(NewRequest)
def app_url(event):
    event.request.set_property(_app_url, 'app_url', reify=True)


def site_layout(function):
    """A decorator that incorporates the site layout template.

    This should only be used on view functions that return dictionaries.
    """
    @wraps(function)
    def wrapped(request, **kwargs):
        renderer = get_renderer('templates/layout.pt')
        info = function(request, **kwargs)
        # Required parameters
        info['_LAYOUT'] = renderer.implementation().macros['layout']
        info['_S'] = lambda x: static_path(request, x)
        # Required parameters that can be overwritten
        info.setdefault('javascripts', None)
        info.setdefault('page_title', None)
        return info
    return wrapped


@site_layout
def use_site_layout(request, *args, **kwargs):
    return kwargs


def static_path(request, *args, **kwargs):
    full_path = request.static_url(*args, _app_url=request.app_url, **kwargs)
    return url_path(full_path)


def url_path(full_path):
    return '/' + full_path.split('/', 3)[-1]


def route_path(request, *args, **kwargs):
    full_path = request.route_url(*args, _app_url=request.app_url, **kwargs)
    return url_path(full_path)
