#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/hardware/tools/kicad10_env.sh"
export LD_LIBRARY_PATH="${KICAD10_ROOT}/usr/lib/x86_64-linux-gnu:${KICAD10_ROOT}/usr/lib:${LD_LIBRARY_PATH:-}"
exec "${KICAD10_ROOT}/usr/bin/python3.11" "${ROOT}/manufacturing/mono_split/tools/make_fab.py" "$@"
