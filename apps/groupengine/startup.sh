#! /bin/sh
exec /app/run-gunicorn-common.sh -k eventlet --workers "${FC_WORKERS}" --worker-connections "${FC_WORKER_CONNECTIONS}" --paste /etc/groupengine.ini
