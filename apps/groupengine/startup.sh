#! /bin/sh
confd -onetime -backend env
exec gunicorn -k eventlet --workers "${FC_WORKERS}" --worker-connections "${FC_WORKER_CONNECTIONS}" --paste /etc/groupengine.ini
