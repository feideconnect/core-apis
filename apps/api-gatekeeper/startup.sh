#! /bin/sh
confd -onetime -backend env
exec pserve /etc/api-gatekeeper.ini
