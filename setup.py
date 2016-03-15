import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

# Prevent pillow from messing up the build system
os.environ['MAX_CONCURRENCY'] = '1'

requires = [
    'aniso8601',
    'blist',
    'cassandra-driver',
    'cherrypy',
    'cryptography',
    'eventlet',
    'futures < 3.0',
    'gunicorn',
    'mock == 1.0.1',
    'pillow',
    'pyramid',
    'pytest',
    'ldap3',
    'pytz',
    'requests',
    'statsd',
    'valideer',
    'webtest',
    ]

setup(name='core-apis',
      version='0.0',
      description='core-apis',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="coreapis",
      dependency_links=[
          'git+https://github.com/feideconnect/python-driver.git@3.0.0-patched#egg=cassandra-driver-3.0.0',
          ],
      entry_points="""\
      [paste.app_factory]
      main = coreapis:main
      [paste.filter_app_factory]
      mockauthmiddleware = coreapis.middleware:mock_main
      cassandramiddleware = coreapis.middleware:cassandra_main
      gkmiddleware = coreapis.middleware:gk_main
      logmiddleware = coreapis.middleware:log_main
      corsmiddleware = coreapis.middleware:cors_main
      """,
      )
