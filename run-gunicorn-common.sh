#!/bin/sh
confd -onetime -backend env
exec gunicorn $EXTRA_ARGS "$@"
