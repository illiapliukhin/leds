#!/usr/bin/env bash
# Download a pinned Freerouting JAR into the ignored tools cache (checksum verified).
set -euo pipefail
VERSION="${1:-2.5.0}"
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_DIR="${TOOLS_DIR}/.cache/freerouting"
mkdir -p "${CACHE_DIR}"
JAR="${CACHE_DIR}/freerouting-${VERSION}.jar"
SHA256="${FREEROUTING_SHA256:-f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7}"
URL="https://github.com/freerouting/freerouting/releases/download/v${VERSION}/freerouting-${VERSION}.jar"
if [[ -f "${JAR}" ]]; then
  if echo "${SHA256}  ${JAR}" | sha256sum -c --status 2>/dev/null; then
    exit 0
  fi
  rm -f "${JAR}"
fi
curl -fsSL -o "${JAR}" "${URL}"
echo "${SHA256}  ${JAR}" | sha256sum -c -
echo "Verified ${JAR}"
