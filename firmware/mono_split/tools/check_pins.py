#!/usr/bin/env python3
"""Verify board_pins.h matches hardware/common/MONO_SPLIT_ARCHITECTURE.md GPIO table."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCH_MD = REPO_ROOT / "hardware/common/MONO_SPLIT_ARCHITECTURE.md"
HEADER = Path(__file__).resolve().parents[1] / "main/board_pins.h"

HEADER_RE = re.compile(
    r'X\((\d+),\s*(\d+),\s*"([^"]+)",\s*"[^"]+"\)',
)


def parse_header(path: Path) -> dict[int, tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    entries: dict[int, tuple[int, str]] = {}
    for gpio, pad, net in HEADER_RE.findall(text):
        entries[int(gpio)] = (int(pad), net)
    return entries


def parse_architecture(path: Path) -> dict[int, tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    section = text.split("## ESP32-S3FN8 GPIO map", 1)
    if len(section) < 2:
        raise RuntimeError("GPIO map section not found in architecture doc")
    table = section[1].split("## ", 1)[0]
    entries: dict[int, tuple[int, str]] = {}

    row_re = re.compile(r"^\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", re.MULTILINE)
    for gpio_field, pad_field, net_cell in row_re.findall(table):
        gpio_field = gpio_field.strip()
        pad_field = pad_field.strip()
        net_cell = net_cell.strip()
        if gpio_field == "GPIO" or gpio_field.startswith("—"):
            continue
        if "…" in gpio_field or re.match(r"13\s*[–-]\s*16", gpio_field):
            gpios = [13, 14, 15, 16]
            pads = [18, 19, 21, 22]
            nets = ["LED_CLK", "LED_SDI", "LED_LE", "LED_OE_N"]
            for gpio, pad, net_name in zip(gpios, pads, nets, strict=True):
                entries[gpio] = (pad, net_name)
            continue
        if re.search(r"[–-]", gpio_field):
            continue
        net_match = re.search(r"`([^`]+)`", net_cell)
        if not net_match:
            continue
        net = net_match.group(1)
        gpio = int(gpio_field)
        pad = int(pad_field)
        entries[gpio] = (pad, net)
    return entries


def main() -> int:
    if not ARCH_MD.is_file():
        print(f"Missing architecture doc: {ARCH_MD}", file=sys.stderr)
        return 2
    if not HEADER.is_file():
        print(f"Missing header: {HEADER}", file=sys.stderr)
        return 2

    header_pins = parse_header(HEADER)
    doc_pins = parse_architecture(ARCH_MD)

    errors = 0
    for gpio in sorted(set(header_pins) | set(doc_pins)):
        header_entry = header_pins.get(gpio)
        doc_entry = doc_pins.get(gpio)
        if header_entry is None:
            print(f"ERROR: GPIO{gpio} in doc missing from board_pins.h: {doc_entry}")
            errors += 1
            continue
        if doc_entry is None:
            print(f"ERROR: GPIO{gpio} in board_pins.h missing from doc: {header_entry}")
            errors += 1
            continue
        if header_entry != doc_entry:
            print(
                f"ERROR: GPIO{gpio} mismatch header={header_entry} doc={doc_entry}",
            )
            errors += 1

    if errors:
        print(f"check_pins: FAILED ({errors} mismatch(es))")
        return 1

    print(f"check_pins: OK ({len(header_pins)} functional GPIO entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
