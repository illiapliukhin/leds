#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:-2.5.0}"
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
VENDOR="${TOOLS_DIR}/vendor"
mkdir -p "${VENDOR}"
JAR="${VENDOR}/freerouting-${VERSION}.jar"
if [[ -f "${JAR}" ]]; then
  echo "Already present: ${JAR}"
  exit 0
fi
URL="https://github.com/freerouting/freerouting/releases/download/v${VERSION}/freerouting-${VERSION}.jar"
curl -fsSL -o "${JAR}" "${URL}"
echo "Downloaded ${JAR}"
