#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCHEMATIC_ROOT="${REPO_ROOT}/hardware/mono_schematic"
# shellcheck source=/dev/null
source "${REPO_ROOT}/hardware/tools/kicad10_env.sh"
export LD_LIBRARY_PATH="${KICAD10_ROOT}/usr/lib/x86_64-linux-gnu:${KICAD10_ROOT}/usr/lib:${LD_LIBRARY_PATH:-}"
REPORT_DIR="${SCHEMATIC_ROOT}/reports"
mkdir -p "${REPORT_DIR}"
# Whole-hierarchy ERC (per-sheet ERC only reports single_global_label noise).
kicad-cli sch erc "${SCHEMATIC_ROOT}/mono_electronics.kicad_sch" -o "${REPORT_DIR}/mono_electronics_erc.json" --format json --severity-all || true
python3 - <<PY
import json
d=json.load(open("${REPORT_DIR}/mono_electronics_erc.json"))
print("ERC violations:", sum(len(s.get("violations",[])) for s in d.get("sheets",[])))
PY
# Real schematic-vs-PCB check from the exported schematic netlist
kicad-cli sch export netlist --format kicadxml -o "${REPORT_DIR}/mono_electronics_sch_netlist.xml" "${SCHEMATIC_ROOT}/mono_electronics.kicad_sch"
python3.11 "${SCHEMATIC_ROOT}/tools/compare_sch_netlist.py" "${REPORT_DIR}/mono_electronics_sch_netlist.xml"
