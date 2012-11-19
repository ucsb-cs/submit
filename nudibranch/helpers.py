import xml.sax.saxutils
from pyramid_addons.helpers import http_bad_request
from .models import File


class DummyTemplateAttr(object):
    def __init__(self, default=None):
        self.default = default

    def __getattr__(self, attr):
        return self.default


def readlines(path):
    with open(path, 'r') as fh:
        return fh.readlines()


def verify_file_ids(request, **kwargs):
    for name, item_id in kwargs.items():
        if item_id:
            item_file = File.fetch_by_id(item_id)
            if not item_file or item_file not in request.user.files:
                return http_bad_request(request, 'Invalid {0}'.format(name))
    return None


def escape(string):
    return xml.sax.saxutils.escape(string, {'"': "&quot;",
                                            "'": "&apos;"})
