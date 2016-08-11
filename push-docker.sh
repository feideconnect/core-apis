base_name=uninett-docker-uninett.bintray.io/dataporten/core-apis

for app in base api-gatekeeper core-apis groupengine
do
    image="${base_name}-${app}"
    docker push "${image}"
done
