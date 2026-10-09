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
FREEROUTING_VERSION = "2.5.0"
FREEROUTING_JAR = (
    TOOLS_DIR / ".cache" / "freerouting" / f"freerouting-{FREEROUTING_VERSION}.jar"
)
MCU_JOIN_LOCK_EAST_MM = 72.0

sys.path.insert(0, str(TOOLS_DIR))

import pcbnew  # noqa: E402
from generate_mono_split_boards import generate_boards  # noqa: E402
from mono_split_esp32 import (  # noqa: E402
    route_mcu_boot_switch,
    route_mcu_enable_joins,
    route_mcu_imu_links,
    route_mcu_led_reserves,
    route_mcu_power_stitch,
    route_mcu_row_address_joins,
    route_mcu_row_xlat_oe,
    route_mcu_strap_passives,
    route_mcu_strap_power_gnd,
    route_mcu_usb,
    route_usb_connector_to_esd,
    route_mcu_xtal_only,
)
from specctra_ses_append import append_specctra_ses_routing  # noqa: E402

MATRIX_LOCKED_CLASS = "matrix_and_fixed"
MCU_ROUTE_CLASS = "mcu_autoroute"

# Hand-routed before export (fixed in DSN); Freerouting does not touch these nets.
HAND_ROUTED_NETS: frozenset[str] = frozenset(
    {
        "XTAL_N",
        "XTAL_P",
    }
)

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
    }
)


def ensure_freerouting_jar() -> Path:
    script = TOOLS_DIR / "download_freerouting.sh"
    if not script.is_file():
        raise FileNotFoundError(script)
    subprocess.run(["bash", str(script), FREEROUTING_VERSION], check=True)
    if not FREEROUTING_JAR.is_file():
        raise FileNotFoundError(f"Freerouting JAR missing after download: {FREEROUTING_JAR}")
    return FREEROUTING_JAR


def _item_x_bounds_mm(item: pcbnew.BOARD_ITEM) -> tuple[float, float]:
    if item.GetClass() == "PCB_VIA":
        position = item.GetPosition()
        x_mm = pcbnew.ToMM(position.x)
        return x_mm, x_mm
    if item.GetClass() == "PCB_TRACK":
        start = item.GetStart()
        end = item.GetEnd()
        x_values = [pcbnew.ToMM(start.x), pcbnew.ToMM(end.x)]
        return min(x_values), max(x_values)
    return 0.0, 0.0


def _track_net_name(item: pcbnew.BOARD_ITEM) -> str:
    net = item.GetNet()
    if net is None or net.GetNetCode() == 0:
        return ""
    return net.GetNetname()


def should_lock_track(item: pcbnew.BOARD_ITEM) -> bool:
    net_name = _track_net_name(item)
    if net_name in HAND_ROUTED_NETS:
        return True
    if net_name not in MCU_AUTOROUTE_NETS:
        return True
    _min_x, max_x = _item_x_bounds_mm(item)
    if max_x < MCU_JOIN_LOCK_EAST_MM:
        return False
    if _min_x >= MCU_JOIN_LOCK_EAST_MM:
        return True
    return False


def strip_mcu_autoroute_copper(board: pcbnew.BOARD) -> int:
    """Remove generator MCU-corner copper so Freerouting owns those nets cleanly."""
    removed = 0
    for item in list(board.GetTracks()):
        net_name = _track_net_name(item)
        if net_name in MCU_AUTOROUTE_NETS:
            board.Remove(item)
            removed += 1
    return removed


def lock_existing_copper(board: pcbnew.BOARD) -> tuple[int, int]:
    """Lock matrix/fixed copper; leave MCU join stubs west of x=72 mm editable."""
    locked = 0
    unlocked = 0
    for item in board.GetTracks():
        if should_lock_track(item):
            item.SetLocked(True)
            locked += 1
        else:
            item.SetLocked(False)
            unlocked += 1
    return locked, unlocked


def refill_copper_zones(board: pcbnew.BOARD) -> None:
    filler = pcbnew.ZONE_FILLER(board)
    zones = board.Zones()
    if not filler.Fill(zones):
        raise RuntimeError("Copper zone fill failed")


def route_mcu_hand_paired_nets(board: pcbnew.BOARD) -> None:
    """40 MHz crystal (scripted, locked); Freerouting routes USB and the rest."""
    route_mcu_xtal_only(board)


def finish_mcu_from_script(board: pcbnew.BOARD) -> None:
    """Scripted fan-in after SES (U1 ↔ reserves / USB / strap)."""
    route_mcu_power_stitch(board)
    route_mcu_strap_passives(board)
    route_mcu_strap_power_gnd(board)
    route_mcu_boot_switch(board)
    route_mcu_row_address_joins(board)
    route_mcu_row_xlat_oe(board)
    route_mcu_led_reserves(board)
    route_mcu_enable_joins(board)
    route_mcu_imu_links(board)
    route_usb_connector_to_esd(board)
    route_mcu_usb(board)


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
    routable = sorted(n for n in net_names if n in MCU_AUTOROUTE_NETS)
    locked_nets = sorted(
        n for n in net_names if n not in MCU_AUTOROUTE_NETS or n in HAND_ROUTED_NETS
    )
    replacement = (
        f"(class {MATRIX_LOCKED_CLASS} {' '.join(locked_nets)}\n"
        f"      {circuit_tail}\n"
        f"    (class {MCU_ROUTE_CLASS} {' '.join(routable)}\n"
        f"      {circuit_tail}\n"
    )
    dsn_path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    print(
        f"Patched DSN net classes: {len(locked_nets)} locked, "
        f"{len(routable)} MCU autoroute"
    )


def freerouting_executable() -> list[str]:
    jar = ensure_freerouting_jar()
    return ["java", "-Xmx8G", "-jar", str(jar)]


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
    strip_mcu_nets: bool,
    script_finish: bool,
) -> None:
    if regenerate:
        generate_boards(REPO_ROOT)

    board = pcbnew.LoadBoard(str(BOARD_PATH))
    route_mcu_hand_paired_nets(board)
    if script_finish:
        finish_mcu_from_script(board)
        refill_copper_zones(board)
        pcbnew.SaveBoard(str(BOARD_PATH), board)
        print(f"Saved {BOARD_PATH} after scripted MCU finish (no Freerouting)")
        return
    if strip_mcu_nets:
        stripped = strip_mcu_autoroute_copper(board)
        print(f"Stripped {stripped} MCU-net items (--strip-mcu-nets)")
    pcbnew.SaveBoard(str(BOARD_PATH), board)

    board = pcbnew.LoadBoard(str(BOARD_PATH))
    if board is None:
        raise RuntimeError(f"Failed to reload {BOARD_PATH}")
    locked, unlocked = lock_existing_copper(board)
    print(
        f"Locked {locked} fixed items; left {unlocked} MCU-join segments "
        f"(west of x={MCU_JOIN_LOCK_EAST_MM} mm) for Freerouting"
    )

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
        "--strip-mcu-nets",
        action="store_true",
        help="Remove generator MCU-net copper before export (experimental)",
    )
    parser.add_argument(
        "--script-finish",
        action="store_true",
        help="Route MCU corner from mono_split_esp32 (no Freerouting)",
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=80,
        help="Freerouting -mp (default 80)",
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
        strip_mcu_nets=args.strip_mcu_nets,
        script_finish=args.script_finish,
    )


if __name__ == "__main__":
    main()
