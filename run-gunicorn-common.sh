#!/bin/sh
confd -onetime -backend env
if [ -n "${FC_STATSD_SERVER}" -a -n "${FC_STATSD_PORT}" -a -n "${FC_STATSD_PREFIX}" -a -n "${DOCKER_HOST}" -a -n "${DOCKER_INSTANCE}" ]; then
    STATSD_PREFIX_HOST="$(echo -n "${DOCKER_HOST}" | tr . _)"
    STATSD_ARGS="--statsd-host ${FC_STATSD_SERVER}:${FC_STATSD_PORT} --statsd-prefix ${FC_STATSD_PREFIX}.${STATSD_PREFIX_HOST}.${DOCKER_INSTANCE}"
else
    STATSD_ARGS=""
fi
exec gunicorn $STATSD_ARGS $EXTRA_ARGS "$@"
