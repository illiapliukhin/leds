#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IDF_DOCKER_IMAGE:-espressif/idf:release-v5.3}"

docker run --rm -v "${ROOT}:/project" -w /project "${IMAGE}" \
  bash -lc 'idf.py set-target esp32s3 && idf.py build'
