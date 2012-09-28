import os
import sys
from setuptools import setup, find_packages

README = open(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                           'README.md')).read()

requires = [
    'pyramid>=1.3',
    'pyramid_addons>=0.5',
    'sqla_mixins>=0.1',
    'sqlalchemy>=0.7.8',
    'zope.sqlalchemy>=0.7.1']

if '--production' == sys.argv[-1]:
    requires.extend(['uwsgi>=1.2.4'])
    sys.argv.pop()
else:
    requires.extend(['pep8', 'pyramid_debugtoolbar', 'waitress'])

setup(name='Nudibranch',
      version='0.0',
      description='Nudibranch',
      long_description=README,
      classifiers=["Programming Language :: Python",
                   "Framework :: Pylons",
                   "Topic :: Internet :: WWW/HTTP",
                   "Topic :: Internet :: WWW/HTTP :: WSGI :: Application", ],
      author='',
      author_email='',
      url='',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="nudibranch",
      entry_points="""\
      [paste.app_factory]
      main = nudibranch:main
      """,
      )
