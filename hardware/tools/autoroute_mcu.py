#!/usr/bin/env python3
"""Freerouting DSN/SES pass for the mono_electronics MCU corner."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
ELECTRONICS_DIR = REPO_ROOT / "hardware" / "mono_electronics"
BOARD_PATH = ELECTRONICS_DIR / "mono_electronics.kicad_pcb"
FREEROUTING_JAR = TOOLS_DIR / "vendor" / "freerouting-2.5.0.jar"
FREEROUTING_CLI = TOOLS_DIR / "vendor" / "freerouting-cli"
FREEROUTING_VERSION = "2.5.0"

sys.path.insert(0, str(TOOLS_DIR))

import pcbnew  # noqa: E402
from generate_mono_split_boards import generate_boards  # noqa: E402
from specctra_ses_append import append_specctra_ses_routing  # noqa: E402
MATRIX_LOCKED_CLASS = "matrix_and_fixed"
MCU_ROUTE_CLASS = "mcu_autoroute"

# Nets whose new copper Freerouting is expected to add (MCU corner + local passives).
MCU_AUTOROUTE_NETS: frozenset[str] = frozenset(
    {
        "AON_3V3",
        "AUDIO_EN",
        "CHIP_PU",
        "DEC_A_EN_N",
        "DEC_B_EN_N",
        "GND",
        "GPIO0_BOOT",
        "IMU_INT1",
        "IMU_SDA",
        "IMU_SCL",
        "LED_CLK",
        "LED_EN",
        "LED_LE",
        "LED_LOGIC_EN",
        "LED_OE_N",
        "LED_SDI",
        "ROW_A0",
        "ROW_A1",
        "ROW_A2",
        "ROW_A3",
        "ROW_XLAT_OE_N",
        "USB_D_N",
        "USB_D_N_MCU",
        "USB_D_P",
        "USB_D_P_MCU",
        "XTAL_N",
        "XTAL_P",
    }
)


def lock_existing_copper(board: pcbnew.BOARD) -> tuple[int, int]:
    """Mark all tracks/vias as locked so Specctra exports them as (type fix)."""
    track_count = 0
    for item in board.GetTracks():
        item.SetLocked(True)
        track_count += 1
    return track_count, 0


def refill_copper_zones(board: pcbnew.BOARD) -> None:
    filler = pcbnew.ZONE_FILLER(board)
    zones = board.Zones()
    if not filler.Fill(zones):
        raise RuntimeError("Copper zone fill failed")


def route_mcu_hand_paired_nets(board: pcbnew.BOARD) -> None:
    """Optional pre-routes before lock/export (default: none — Freerouting owns MCU corner)."""


def patch_dsn_net_classes(dsn_path: Path) -> None:
    """Split KiCad's single netclass so Freerouting -inc skips matrix/fixed nets."""
    text = dsn_path.read_text(encoding="utf-8")
    marker = "(class kicad_default "
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("DSN missing kicad_default netclass")
    depth = 0
    end = start
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    block = text[start:end]
    circuit_index = block.index("(circuit")
    net_blob = block[len("(class kicad_default ") : circuit_index]
    net_names = net_blob.split()
    circuit_tail = block[circuit_index:]
    mcu_nets = sorted(n for n in net_names if n in MCU_AUTOROUTE_NETS)
    locked_nets = sorted(n for n in net_names if n not in MCU_AUTOROUTE_NETS)
    replacement = (
        f"(class {MATRIX_LOCKED_CLASS} {' '.join(locked_nets)}\n"
        f"      {circuit_tail}\n"
        f"    (class {MCU_ROUTE_CLASS} {' '.join(mcu_nets)}\n"
        f"      {circuit_tail}\n"
    )
    dsn_path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    print(
        f"Patched DSN net classes: {len(locked_nets)} locked, {len(mcu_nets)} MCU autoroute"
    )


def freerouting_executable() -> list[str]:
    # Prefer the JAR on OpenJDK 25+: the GraalVM freerouting-cli binary can crash
    # during snapshot serialization on headless CI/agents.
    if FREEROUTING_JAR.is_file():
        return ["java", "-Xmx8G", "-jar", str(FREEROUTING_JAR)]
    if FREEROUTING_CLI.is_file():
        return [str(FREEROUTING_CLI)]
    raise FileNotFoundError(
        f"Install Freerouting {FREEROUTING_VERSION} under hardware/tools/vendor/ "
        "(freerouting-cli or freerouting-{version}.jar + OpenJDK 25)."
    )


def run_freerouting(
    dsn_path: Path,
    ses_path: Path,
    *,
    max_passes: int,
    threads: int,
) -> None:
    command = [
        *freerouting_executable(),
        "--gui.enabled=false",
        "-de",
        str(dsn_path),
        "-do",
        str(ses_path),
        f"-mp{max_passes}",
        f"-mt{threads}",
        "-inc",
        MATRIX_LOCKED_CLASS,
        "--router.autorouter.save_intermediate_stages=false",
        "--router.fanout.enabled=false",
        "--router.fanout.ripup_allowed=false",
        "--router.layers.routable=true,true,true,true",
        "--router.layers.preferred_direction_horizontal=true,false,true,false",
    ]
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)


def autoroute(
    *,
    regenerate: bool,
    max_passes: int,
    threads: int,
    skip_freerouting: bool,
) -> None:
    if regenerate:
        generate_boards(REPO_ROOT)

    board = pcbnew.LoadBoard(str(BOARD_PATH))
    route_mcu_hand_paired_nets(board)
    pcbnew.SaveBoard(str(BOARD_PATH), board)

    board = pcbnew.LoadBoard(str(BOARD_PATH))
    locked, _ = lock_existing_copper(board)
    print(f"Locked {locked} track/via items (Specctra type fix)")

    dsn_path = ELECTRONICS_DIR / "mono_electronics.dsn"
    ses_path = ELECTRONICS_DIR / "mono_electronics.ses"
    stale_rules = ELECTRONICS_DIR / "mono_electronics.rules"
    if stale_rules.is_file():
        stale_rules.unlink()

    if not pcbnew.ExportSpecctraDSN(board, str(dsn_path)):
        raise RuntimeError(f"ExportSpecctraDSN failed for {BOARD_PATH}")
    patch_dsn_net_classes(dsn_path)
    print(f"Exported DSN ({dsn_path.stat().st_size // 1024} KiB)")

    if skip_freerouting:
        return

    run_freerouting(dsn_path, ses_path, max_passes=max_passes, threads=threads)

    if not ses_path.is_file():
        raise RuntimeError(f"Freerouting did not create {ses_path}")

    board = pcbnew.LoadBoard(str(BOARD_PATH))
    wires, vias = append_specctra_ses_routing(board, ses_path)
    print(f"Appended SES routing: {wires} wire paths, {vias} vias (existing copper kept)")

    refill_copper_zones(board)
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print(f"Saved {BOARD_PATH} after SES append")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-regenerate",
        action="store_true",
        help="Skip generate_mono_split_boards (use existing .kicad_pcb)",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Generate + lock + export DSN/rules only",
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=40,
        help="Freerouting -mp (default 40)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=max(1, __import__("os").cpu_count() or 4) - 1,
        help="Freerouting -mt",
    )
    args = parser.parse_args()
    autoroute(
        regenerate=not args.no_regenerate,
        max_passes=args.max_passes,
        threads=args.threads,
        skip_freerouting=args.export_only,
    )


if __name__ == "__main__":
    main()
