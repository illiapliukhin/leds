#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=hardware/tools/kicad10_env.sh
source "${ROOT}/hardware/tools/kicad10_env.sh"
exec python3.11 "${ROOT}/hardware/tools/autoroute_mcu.py" "$@"
