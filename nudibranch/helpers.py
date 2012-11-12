class DummyTemplateAttr(object):
    def __init__(self, default=None):
        self.default = default

    def __getattr__(self, attr):
        return self.default


def readlines(path):
    with open(path, 'r') as fh:
        return fh.readlines()
