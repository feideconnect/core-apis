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
    'coverage',
    'cryptography',
    'eventlet ~= 0.22.1',
    'futures ~= 3.2',
    'gunicorn',
    'pillow ~= 5.1',
    'pylint',
    'pyramid ~= 1.9.2',
    'pytest-cov',
    'pytest',
    'ldap3 ~= 2.5',
    'pytz',
    'requests',
    'six ~= 1.11.0',
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
      entry_points="""\
      [paste.app_factory]
      main = coreapis:main
      [paste.filter_app_factory]
      mockauthmiddleware = coreapis.middleware:mock_main
      cassandramiddleware = coreapis.middleware:cassandra_main
      gkmiddleware = coreapis.middleware:gk_main
      logmiddleware = coreapis.middleware:log_main
      corsmiddleware = coreapis.middleware:cors_main
      ratelimitmiddleware = coreapis.middleware:ratelimit_main
      gatekeepedmiddleware = coreapis.middleware:gatekeeped_mw_main
      """,
      )
