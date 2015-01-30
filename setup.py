"""Submit setup.py."""

import os
import re
import sys
from setuptools import setup, find_packages

PACKAGE_NAME = 'submit'
HERE = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(HERE, 'README.md')) as fp:
    README = fp.read()
with open(os.path.join(HERE, PACKAGE_NAME, '__init__.py')) as fp:
    VERSION = re.search("__version__ = '([^']+)'", fp.read()).group(1)

requires = [
    'alembic>=0.6.3',
    'amqp_worker>=0.2',
    'diff-match-patch==20120106',
    'numpy>=1.8.0',
    'python-ldap>=2.4.14',
    'pastescript>=1.7.5',
    'pika>=0.9.6',
    'pyramid>=1.5.2',
    'pyramid_addons>=0.20',
    'pyramid_chameleon>=0.1',
    'pyramid_exclog>=0.7',
    'pyramid_layout>=0.8',
    'pyramid_mailer>=0.10',
    'pyramid_tm>=0.5',
    'python-daemon>=1.5.5',
    'python-dateutil>=2.1',
    'sqla_mixins>=0.6',
    'sqlalchemy>=0.7.8',
    'zope.sqlalchemy>=0.7.1']

if '--production' == sys.argv[-1]:
    requires.extend(['psycopg2', 'uwsgi>=1.2.4'])
    sys.argv.pop()
else:
    requires.extend(['flake8', 'pyramid_debugtoolbar', 'waitress'])

setup(name=PACKAGE_NAME,
      version=VERSION,
      description=('submit is a submission web service designed for '
                   'programming assignments'),
      long_description=README,
      classifiers=["Programming Language :: Python",
                   "Framework :: Pylons",
                   "Topic :: Internet :: WWW/HTTP",
                   "Topic :: Internet :: WWW/HTTP :: WSGI :: Application", ],
      author='Bryce Boe',
      author_email='bboe@cs.ucsb.edu',
      url='https://github.com/ucsb-cs/submit',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      entry_points="""\
      [paste.app_factory]
      main = {package}:main
      [console_scripts]
      worker_verification = {package}.workers.verification:main
      worker_proxy = {package}.workers.proxy:main
      """.format(package=PACKAGE_NAME),
      )
