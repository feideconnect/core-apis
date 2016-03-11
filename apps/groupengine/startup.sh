#! /bin/sh
confd -onetime -backend env
exec gunicorn -k eventlet --workers "${FC_WORKERS}" --threads "${FC_THREADS}" --paste /etc/groupengine.ini
