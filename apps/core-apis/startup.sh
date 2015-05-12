#! /bin/sh
confd -onetime -backend env
exec pserve /etc/core-apis.ini
