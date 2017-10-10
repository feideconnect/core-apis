#!/bin/bash
set -e
export COMPOSE_FILE=compose-test-cassandra.yml

# Set up cassandra test environment
docker-compose pull
docker-compose up -d cassandra
docker-compose up -d ldap
function clean-docker() {
    docker-compose kill
    docker-compose rm --force --all
}
trap clean-docker EXIT

docker-compose build coreapis
docker-compose run coreapis sh -c "pylint -f parseable coreapis >pylint.out || true"

docker-compose run dataportenschemas

docker-compose run coreapis sh -c "coverage run --concurrency eventlet --branch -m py.test --junitxml=testresults.xml || true"
docker-compose run coreapis sh -c "coverage html --include 'coreapis/*'"
docker-compose run coreapis sh -c "coverage xml --include 'coreapis/*'"
