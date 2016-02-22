#! /bin/sh
set -e
base_name=uninett-docker-uninett.bintray.io/dataporten/core-apis
docker build -t ${base_name}-base:latest --build-arg GIT_COMMIT="${GIT_COMMIT}" --build-arg JENKINS_BUILD_NUMBER="${BUILD_NUMBER}" .
base_dir=$(pwd)
for app in api-gatekeeper core-apis groupengine
do
    cd "${base_dir}/apps/${app}"
    image="${base_name}-${app}"
    docker build -t ${image}:latest .
done
