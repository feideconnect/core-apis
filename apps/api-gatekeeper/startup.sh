#! /bin/sh
confd -onetime -backend env
exec gunicorn $EXTRA_ARGS --workers "${FC_WORKERS}" --threads "${FC_THREADS}" --paste /etc/api-gatekeeper.ini
