#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCHEMATIC_ROOT="${REPO_ROOT}/hardware/mono_schematic"
# shellcheck source=/dev/null
source "${REPO_ROOT}/hardware/tools/kicad10_env.sh"
export LD_LIBRARY_PATH="${KICAD10_ROOT}/usr/lib/x86_64-linux-gnu:${KICAD10_ROOT}/usr/lib:${LD_LIBRARY_PATH:-}"
REPORT_DIR="${SCHEMATIC_ROOT}/reports"
mkdir -p "${REPORT_DIR}"
TOTAL=0
for schematic_file in "${SCHEMATIC_ROOT}/mono_electronics.kicad_sch" "${SCHEMATIC_ROOT}"/sheets/*.kicad_sch; do
  base_name="$(basename "${schematic_file}" .kicad_sch)"
  echo "ERC ${base_name}..."
  kicad-cli sch erc "${schematic_file}" \
    -o "${REPORT_DIR}/${base_name}_erc.json" \
    --format json \
    --severity-all || true
  count="$(python3 - <<PY
import json
from pathlib import Path
path = Path("${REPORT_DIR}/${base_name}_erc.json")
data = json.loads(path.read_text())
print(sum(len(sheet.get("violations", [])) for sheet in data.get("sheets", [])))
PY
)"
  echo "  violations: ${count}"
  TOTAL=$((TOTAL + count))
done
echo "Total ERC violations (see ERC_WAIVERS.md): ${TOTAL}"
