FROM uninett-docker-uninett.bintray.io/jessie/base
RUN apt-get update
# Setup locales
RUN sh -c 'echo "en_US.UTF-8 UTF-8" > /etc/locale.gen' && RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y locales && locale-gen
ENV LC_ALL=en_US.UTF-8
# Install dependencies
RUN RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates \
  gcc \
  libffi-dev \
  libjpeg-dev \
  libssl-dev \
  python3 \
  python3-dev \
  zlib1g-dev \
  git
RUN RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y -t jessie-backports python3-setuptools
# Install confd
RUN wget -O /usr/local/bin/confd https://github.com/kelseyhightower/confd/releases/download/v0.9.0/confd-0.9.0-linux-amd64 && chmod 0755 /usr/local/bin/confd
# Install app
ADD . /app
WORKDIR /app
RUN python3 setup.py develop
ARG GIT_COMMIT
ENV GIT_COMMIT ${GIT_COMMIT}
ARG JENKINS_BUILD_NUMBER
ENV JENKINS_BUILD_NUMBER ${JENKINS_BUILD_NUMBER}
LABEL no.uninett.dataporten.git_commit="${GIT_COMMIT}"
LABEL no.uninett.dataporten.jenkins_build="${JENKINS_BUILD_NUMBER}"
