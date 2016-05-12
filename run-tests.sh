#!/bin/bash
set -e
export COMPOSE_FILE=compose-test-cassandra.yml
KEYSPACE=test_coreapis

# Set up cassandra test environment
docker-compose up -d
function clean-docker() {
    docker-compose kill
    docker-compose rm --force --all
}
trap clean-docker EXIT

echo "Waiting schema setup to complete"
while ! docker-compose ps | grep -q 'dataportenschemas.*Exit'; do
    sleep 0.1
done
echo "Done"

export DP_CASSANDRA_TEST_NODE=$(docker-compose port cassandra 9042)
export DP_CASSANDRA_TEST_KEYSPACE=$KEYSPACE

pip install pylint
pip install coverage
pip install --upgrade setuptools
python setup.py develop
pylint -f parseable coreapis >pylint.out || true
echo "pylint returned $result"
coverage run --branch -m py.test --junitxml=testresults.xml || true
coverage html --include 'coreapis/*'
coverage xml --include 'coreapis/*'
