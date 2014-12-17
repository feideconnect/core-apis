Core apis and authorization middleware for feide connect.

To run:
Copy development.ini.example to development.ini and change statsd_server, contact_points and keyspace to proper values. Then, assuming python3 is installed and virtualenvwrapper is configured, run these commands:

mkvirtualenv -p `which python3` feideconnect
python setup.py develop
pserver --reload development.ini


To run unit tests:
py.test -v coreapis/tests.py
