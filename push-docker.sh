base_name=registry.uninett.no/public/dataporten-core-apis

for app in base api-gatekeeper core-apis groupengine clientadm apigkadm
do
    image="${base_name}-${app}"
    docker push "${image}"
done
