#!/bin/sh
set -e
COMPOSEFILE=compose-test-cassandra.yml
KEYSPACE=test_coreapis

# Set up cassandra test environment
pip install docker-compose==1.5.2
docker-compose -f $COMPOSEFILE pull
docker-compose -f $COMPOSEFILE run -e DP_CASSANDRA_TEST_KEYSPACE=$KEYSPACE \
    core-apis python3 bin/init_keyspace.py -fw
docker-compose -f $COMPOSEFILE run -e CASSANDRA_KEYSPACE=$KEYSPACE dataportenschemas up
DP_CASSANDRA_TEST_NODE=$(docker-compose -f $COMPOSEFILE run core-apis env \
    | grep ^CASSANDRA_PORT_9042_TCP_ADDR | cut -d= -f2)
export DP_CASSANDRA_TEST_NODE
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

# Tear down cassandra test environment
docker-compose -f $COMPOSEFILE kill cassandra
docker-compose -f $COMPOSEFILE rm -fv cassandra
