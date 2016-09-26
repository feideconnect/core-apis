#!/bin/bash
set -e
export COMPOSE_FILE=compose-test-cassandra.yml

# Set up cassandra test environment
docker-compose pull
docker-compose up -d
function clean-docker() {
    docker-compose kill
    docker-compose rm --force --all
}
trap clean-docker EXIT

export DP_CASSANDRA_TEST_NODE=localhost
export DP_CASSANDRA_TEST_KEYSPACE=test_coreapis

pip install pylint
pip install coverage
pip install --upgrade setuptools
python setup.py develop
pylint -f parseable coreapis >pylint.out || true
echo "pylint returned $result"

echo "Waiting schema setup to complete"
while ! docker-compose ps 2>/dev/null | grep -q 'dataportenschemas.*Exit'; do
    sleep 0.1
done
echo "Done"


coverage run --branch -m py.test --junitxml=testresults.xml || true
coverage html --include 'coreapis/*'
coverage xml --include 'coreapis/*'
