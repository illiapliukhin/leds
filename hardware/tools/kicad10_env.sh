#!/usr/bin/env bash
# KiCad 10 AppImage root (pcbnew + kicad-cli for mono split generators).
KICAD10_ROOT="${KICAD10_ROOT:-/workspace/.kicad10/squashfs-root}"
export PATH="${KICAD10_ROOT}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${KICAD10_ROOT}/usr/lib/x86_64-linux-gnu:${KICAD10_ROOT}/usr/lib:${LD_LIBRARY_PATH:-}"
