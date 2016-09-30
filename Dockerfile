FROM uninett-docker-uninett.bintray.io/jessie/base
RUN apt-get update
# Setup locales
ENV LC_ALL=en_US.UTF-8
# Install dependencies
RUN apt-get update && RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ca-certificates \
  gcc \
  libffi-dev \
  libjpeg-dev \
  libssl-dev \
  locales \
  python3 \
  python3-dev \
  zlib1g-dev \
  git \
  && RUNLEVEL=1 DEBIAN_FRONTEND=noninteractive apt-get install -y -t jessie-backports python3-setuptools --no-install-recommends \
  && rm -rf /var/lib/apt/lists/*

RUN sh -c 'echo "en_US.UTF-8 UTF-8" > /etc/locale.gen' && locale-gen

# Install confd
RUN wget -O /usr/local/bin/confd https://github.com/kelseyhightower/confd/releases/download/v0.9.0/confd-0.9.0-linux-amd64 && chmod 0755 /usr/local/bin/confd
# Install app
COPY . /app
WORKDIR /app
RUN python3 setup.py develop
ARG GIT_COMMIT
ENV GIT_COMMIT ${GIT_COMMIT}
ARG JENKINS_BUILD_NUMBER
ENV JENKINS_BUILD_NUMBER ${JENKINS_BUILD_NUMBER}
LABEL no.uninett.dataporten.git_commit="${GIT_COMMIT}"
LABEL no.uninett.dataporten.jenkins_build="${JENKINS_BUILD_NUMBER}"
