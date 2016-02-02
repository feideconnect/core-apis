#!/bin/sh

set -e
pip install pylint
pip install coverage
pip install --upgrade setuptools
python setup.py develop
pylint -f parseable coreapis >pylint.out || result=$?
echo "pylint returned $result"
coverage run --branch -m py.test --junitxml=testresults.xml || true
res=$(($result&35))
coverage html --include 'coreapis/*'
coverage xml --include 'coreapis/*'
exit 0
