
Core apis and authorization middleware for feide connect.

Core APIs is a component of the [UNINETT Connect Platform](http://feideconnect.no).



## Running Core-APIs

To run:

Copy `development.ini.example` to `development.ini` and change `statsd_server`, `contact_points` and keyspace to proper values.

Create an `ldap-config.json` file (look at `ldap-config.json.example` for syntax)

Make sure that libjpeg-dev, libffi-dev, libssl-dev and zlib1g-dev are installed

	apt-get install libjpeg-dev libffi-dev libssl-dev zlib1g-dev on Debian/Ubuntu


Then, assuming python3 is installed and virtualenvwrapper is configured, run these commands:

	mkvirtualenv -p `which python3` feideconnect
	python setup.py develop
	pserve --reload development.ini


## Requirements

Requires Python 3.3 or newer. Debian Wheezy has 3.2, which is too old.


## Running the tests

To run unit tests:

	py.test -v coreapis
