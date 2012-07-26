import os
import sys
from setuptools import setup, find_packages

README = open(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                           'README.md')).read()

requires = [
    'pyramid',
    'pytz',
    'sqla_mixins',
    'sqlalchemy',
    'zope.sqlalchemy']

if '--production' == sys.argv[-1]:
    requires.extend(['uwsgi'])
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
