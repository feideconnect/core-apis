#!/usr/bin/env bash

if [ "$SONAR_BRANCH" == "$SONAR_BRANCH_TARGET" ]
then
    TARGET_ARG=""
else
    TARGET_ARG=" -Dsonar.branch.target=${SONAR_BRANCH_TARGET}"
fi

sonar-scanner \
  -Dsonar.login=${SONAR_KEY} \
  -Dsonar.projectVersion=${SONAR_PROJECT_VERSION:0:8} \
  -Dsonar.branch.name=${SONAR_BRANCH} \
  ${TARGET_ARG}
