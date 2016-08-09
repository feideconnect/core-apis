base_name=uninett-docker-uninett.bintray.io/dataporten/core-apis

docker push "${base_name}"
for app in api-gatekeeper core-apis groupengine
do
    image="${base_name}-${app}"
    docker push "${image}"
done
