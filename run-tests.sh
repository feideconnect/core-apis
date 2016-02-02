#!/bin/sh

set -e
pip install pylint
pip install coverage
pip install --upgrade setuptools
python setup.py develop
pylint -f parseable coreapis >pylint.out || true
echo "pylint returned $result"
coverage run --branch -m py.test --junitxml=testresults.xml || true
coverage html --include 'coreapis/*'
coverage xml --include 'coreapis/*'
