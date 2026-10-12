#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ -z "${IDF_PATH:-}" ]]; then
  if [[ -f "${HOME}/esp/esp-idf/export.sh" ]]; then
    # shellcheck disable=SC1091
    source "${HOME}/esp/esp-idf/export.sh"
  else
    echo "IDF_PATH not set and ~/esp/esp-idf not found. Use build_in_docker.sh or install ESP-IDF." >&2
    exit 1
  fi
fi

python3 tools/check_pins.py
idf.py set-target esp32s3
idf.py build
