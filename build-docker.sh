#! /bin/sh
set -e
base_name=uninett-docker-uninett.bintray.io/feideconnect/core-apis
docker build -t ${base_name}-base:$GIT_COMMIT .
docker tag -f ${base_name}-base:$GIT_COMMIT ${base_name}-base:latest
base_dir=$(pwd)
for app in api-gatekeeper core-apis groupengine
do
    cd "${base_dir}/apps/${app}"
    image="${base_name}-${app}"
    docker build -t ${image}:$GIT_COMMIT .
    docker tag -f ${image}:$GIT_COMMIT ${image}:latest
done
