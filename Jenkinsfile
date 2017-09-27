node {
    checkout scm

    stage('Test') {
        wrap([$class: 'AnsiColorBuildWrapper', 'colorMapName': 'XTerm']) {
            sh "CASS_DRIVER_NO_CYTHON=1 ./run-tests.sh"
        }

        junit "testresults.xml"
        step([$class: 'CoberturaPublisher', coberturaReportFile: 'coverage.xml'])
        publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'htmlcov', reportFiles: 'index.html', reportName: 'Code coverage'])
    }

    stage('Build') {
        base_name = "registry.uninett.no/public/dataporten-core-apis"
        args = "--pull --no-cache  --build-arg GIT_COMMIT='${env.GIT_COMMIT}' --build-arg JENKINS_BUILD_NUMBER='${env.BUILD_NUMBER}' ."
        images = []
        images.add(docker.build(base_name, args))
        for (app in ['api-gatekeeper', 'core-apis groupengine', 'clientadm', 'apigkadm']) {
            image='${base_name}-${app}'
            images.add(docker.build(image))
        }
        for (image in images) {
            image.push()
        }
    }
}
