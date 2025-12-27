pipeline {
  agent any

  options {
    timestamps()
    //ansiColor('xterm')
    disableConcurrentBuilds() // prevent 2 jobs writing to the same dirs
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }

  parameters {
    string(name: 'START', defaultValue: '1600', description: 'TWIC start number')
    string(name: 'END', defaultValue: '', description: 'TWIC end number (if empty go up to 404)')
    booleanParam(name: 'EXTRACT', defaultValue: true, description: 'Extract PGN from ZIP')
    booleanParam(name: 'MERGE', defaultValue: true, description: 'Merge PGN into one file')
    string(name: 'SLEEP', defaultValue: '1.0', description: 'time between requests (in seconds)')
    string(name: 'MAX_MISSES', defaultValue: '3', description: 'How many 404')
  }

  environment {
    // outcome and cache in workspace - easy archive artifacts
    OUT_DIR = "twic_download"
    VENV_DIR = ".venv"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Setup Python') {
      steps {
        sh '''
          set -euxo pipefail
          python3 -V
          python3 -m venv "${VENV_DIR}"
          . "${VENV_DIR}/bin/activate"
          pip install --upgrade pip
          pip install -r requirements.txt
        '''
      }
    }

    stage('Prepare output dir') {
      steps {
        sh '''
          set -euxo pipefail
          mkdir -p "${OUT_DIR}"
        '''
      }
    }

    stage('Run downloader') {
      steps {
        sh '''
          set -euxo pipefail
          . "${VENV_DIR}/bin/activate"

          ARGS="--start ${START} --out ${OUT_DIR} --sleep ${SLEEP} --max-misses ${MAX_MISSES}"

          # end optional
          if [ -n "${END}" ]; then
            ARGS="$ARGS --end ${END}"
          fi

          if [ "${EXTRACT}" = "true" ]; then
            ARGS="$ARGS --extract"
          fi

          if [ "${MERGE}" = "true" ]; then
            # merge only after extract / script will communicate that
            ARGS="$ARGS --merge ${OUT_DIR}/merged.pgn"
          fi

          echo "Running: python3 -u twic_dl.py $ARGS"
          python3 -u twic_dl.py $ARGS
        '''
      }
    }

    stage('Archive artifacts') {
      steps {
        // archive zip and pgns
        archiveArtifacts artifacts: "${OUT_DIR}/**", fingerprint: true, onlyIfSuccessful: false
      }
    }
  }

  post {
    always {
      sh '''
        set +e
        echo "Workspace:"
        pwd
        ls -la

        if [ -d "${OUT_DIR}" ]; then
          echo "Contents of ${OUT_DIR}:"
          find "${OUT_DIR}" -maxdepth 3 -type f -print || true
          du -sh "${OUT_DIR}" || true
        else
          echo "No ${OUT_DIR} directory created in this build."
        fi
      '''
    }
  }
}
