import xml.sax.saxutils
from pyramid_addons.helpers import http_bad_request


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


def next_in_sorted(item, lst):
    '''Returns the next item in the given (assumed sorted) list,
    or None if it is already the last item.  Throws an IndexError if
    it doesn't exist at all'''
    retval_idx = lst.index(item) + 1
    return lst[retval_idx] if retval_idx < len(lst) else None
