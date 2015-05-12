FROM uninett-docker-uninett.bintray.io/jessie/base
RUN apt-get update
# Setup locales
RUN sh -c 'echo "en_US.UTF-8 UTF-8" > /etc/locale.gen'
RUN RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y locales
RUN locale-gen
ENV LC_ALL=en_US.UTF-8
# Install base os stuff
RUN RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates
# Install python core
RUN RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-setuptools python3-dev
# Install binary dependencies
RUN RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential libjpeg-dev libffi-dev libssl-dev zlib1g-dev
ADD . /app
WORKDIR /app
RUN python3 setup.py install
RUN wget -O /usr/local/bin/confd https://github.com/kelseyhightower/confd/releases/download/v0.9.0/confd-0.9.0-linux-amd64
RUN chmod 0755 /usr/local/bin/confd
