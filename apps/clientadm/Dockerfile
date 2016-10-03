FROM uninett-docker-uninett.bintray.io/dataporten/core-apis-base
RUN mkdir -p /etc/confd
ADD conf.d /etc/confd/conf.d
ADD templates /etc/confd/templates
ADD startup.sh /startup.sh
ENTRYPOINT ["/startup.sh"]
