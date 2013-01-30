import os
import sys
from setuptools import setup, find_packages

README = open(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                           'README.md')).read()

requires = [
    'alembic>=0.4.0',
    'amqp_worker>=0.0.5',
    'mock>=1.0.0',
    'pika>=0.9.6',
    'pyramid>=1.4',
    'pyramid_addons>=0.11',
    'pyramid_mailer>=0.10',
    'pyramid_tm>=0.5',
    'python-daemon>=1.5.5',
    'sqla_mixins>=0.6',
    'sqlalchemy>=0.7.8',
    'zope.sqlalchemy>=0.7.1']

if '--production' == sys.argv[-1]:
    requires.extend(['psycopg2', 'uwsgi>=1.2.4'])
    sys.argv.pop()
else:
    requires.extend(['flake8', 'pyramid_debugtoolbar', 'waitress'])

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
      [console_scripts]
      worker_verification = nudibranch.workers.verification:main
      worker_sync_files = nudibranch.workers.communicator:sync_files
      worker_fetch_results = nudibranch.workers.communicator:fetch_results
      """,
      )
