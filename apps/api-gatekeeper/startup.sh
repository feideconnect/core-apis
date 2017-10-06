#! /bin/sh
exec /app/run-gunicorn-common.sh --workers "${FC_WORKERS}" --threads "${FC_THREADS}" --paste /etc/api-gatekeeper.ini
