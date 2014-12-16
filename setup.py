import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'blist',
    'cassandra-driver',
    'cherrypy',
    'pyramid',
    'pytest',
    'pytz',
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
      """,
      )
