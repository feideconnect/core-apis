#!/bin/bash
set -e
export COMPOSE_FILE=compose-test-cassandra.yml

up_services=$(docker-compose ps|grep -c Up||true)
if [ $up_services -eq 3 ]
then
    do_setup=0
else
    do_setup=1
fi

# Set up cassandra test environment
if [ $do_setup -eq 1 ]
then
    docker-compose pull
    docker-compose up -d
fi
function clean-docker() {
    docker-compose kill
    docker-compose rm --force -v
}
if test -z "${NO_CLEANUP}"
then
    trap clean-docker EXIT
fi

if [ -z "${NO_PYLINT}" ]
then
    docker-compose exec -T -u ${UID}:${GID} coreapis sh -c "pylint -f parseable coreapis >pylint.out || true"
fi

docker-compose exec -T -u ${UID}:${GID} coreapis sh -c "py.test -m 'not eventlet' --cov --cov-report=html --cov-report=xml --junitxml=testresults.xml $@||true"
docker-compose exec -T -u ${UID}:${GID} coreapis sh -c "py.test -m eventlet --cov --cov-append --cov-report=html --cov-report=xml --junitxml=testresults-eventlet.xml $@||true"
