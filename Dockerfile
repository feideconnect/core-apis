FROM registry.uninett.no/public/jessie:minbase
# Setup locales
ENV LC_ALL=en_US.UTF-8
# Install dependencies
RUN install_packages.sh python3 python3-six python3-requests locales ca-certificates libjpeg62 libpng12-0

RUN sh -c 'echo "en_US.UTF-8 UTF-8" > /etc/locale.gen' && locale-gen

# Install confd
RUN /usr/local/sbin/with_packages.sh "wget" "wget -O /usr/local/bin/confd https://github.com/kelseyhightower/confd/releases/download/v0.9.0/confd-0.9.0-linux-amd64 && chmod 0755 /usr/local/bin/confd"
# Install app
COPY . /app
WORKDIR /app
RUN with_packages.sh "gcc libffi-dev libjpeg-dev libssl-dev python3-dev zlib1g-dev git python3-pip" "pip3 install --upgrade setuptools && python3 setup.py develop"
ARG GIT_COMMIT
ENV GIT_COMMIT ${GIT_COMMIT}
ARG JENKINS_BUILD_NUMBER
ENV JENKINS_BUILD_NUMBER ${JENKINS_BUILD_NUMBER}
LABEL no.uninett.dataporten.git_commit="${GIT_COMMIT}"
LABEL no.uninett.dataporten.jenkins_build="${JENKINS_BUILD_NUMBER}"
