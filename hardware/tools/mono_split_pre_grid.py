"""Fixed MCU escapes applied before grid geometry dump (strap / USB / DEC / AON)."""

from __future__ import annotations

import pcbnew

from mono_split_esp32 import (
    route_mcu_aon_north_and_cap,
    route_mcu_decoder_enables,
    route_mcu_strap_passives,
    route_mcu_usb,
)


def apply_pre_grid_mcu_fixtures(board: pcbnew.BOARD) -> None:
    route_mcu_strap_passives(board)
    route_mcu_usb(board, only_mcu_nets={"USB_D_N_MCU"})
    route_mcu_decoder_enables(board, only_nets={"DEC_A_EN_N"})
    route_mcu_aon_north_and_cap(board)
