#! /bin/sh
confd -onetime -backend env
exec gunicorn -k eventlet --paste /etc/groupengine.ini
