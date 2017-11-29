#!/bin/bash
set -e
export COMPOSE_FILE=compose-test-cassandra.yml

# Set up cassandra test environment
docker-compose pull
docker-compose up -d cassandra
docker-compose up -d ldap
function clean-docker() {
    docker-compose kill
    docker-compose rm --force -v
}
if test -z "${NO_CLEANUP}"
then
    trap clean-docker EXIT
fi

docker-compose build coreapis
docker-compose run coreapis sh -c "pylint -f parseable coreapis >pylint.out || true"

docker-compose run dataportenschemas

docker-compose run -u ${UID}:${GID} coreapis sh -c "py.test --cov --cov-report=html --cov-report=xml --junitxml=testresults.xml $@"
