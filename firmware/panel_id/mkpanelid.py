#!/usr/bin/env python3
"""Build a 256-byte panel-ID EEPROM image (LED_INTERFACE_STANDARD v1).
   ./mkpanelid.py --preset garland32 --serial 7 -o garland32.bin
Program with any 24C02 programmer, or from the ESP32 over the ID bus (WP is tied low)."""
import argparse, struct
FMT = '<IBBBBBBHHHHBBHHHHI16sIIH4sH'
assert struct.calcsize(FMT) == 64
PRESETS = {  # class, led, rows, cols, pitch_um, i_led_ua, i_row_ma, vf_mv, map, flags, blank, prediss, row_mohm, name
 'flat32':     (0, 0, 32, 32, 4000, 10000, 320, 3000, 0, 0, 2000, 0, 300, 'mono32_flat'),
 'flat20':     (0, 0, 20, 20, 6000, 10000, 200, 3000, 0, 0, 2000, 0, 300, 'mono20_flat'),
 'lattice32':  (1, 0, 32, 32, 4000, 10000, 320, 3000, 0, 0, 2000, 0, 300, 'mono32_lattice'),
 'full32':     (2, 0, 32, 32, 4000, 10000, 320, 3000, 0, 0, 2000, 0, 300, 'mono32_full'),
 'garland32':  (3, 0, 32, 32, 0, 8000, 256, 3000, 0, 2, 8000, 1500, 1200, 'garland32'),
}
def crc16(b):
    c = 0xFFFF
    for x in b:
        c ^= x << 8
        for _ in range(8): c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c
def build(p, serial=0, hw_rev=1, row_mask=0xFFFFFFFF, col_mask=0xFFFFFFFF, table_id=0):
    cl, led, r, c, pitch, ia, ir, vf, mp, fl, bl, pd, rm, name = p
    body = struct.pack(FMT, 0x5044454C, 1, 64, cl, led, r, c, pitch, ia, ir, vf, mp, fl, bl, pd, rm, hw_rev,
                       serial, name.encode()[:16].ljust(16, b'\0'), row_mask, col_mask, table_id, b'\0' * 4, 0)
    rec = body[:0x3E] + struct.pack('<H', crc16(body[:0x3E]))
    return rec + b'\xff' * (256 - 64)
if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('--preset', choices=PRESETS, required=True)
    a.add_argument('--serial', type=int, default=0); a.add_argument('-o', required=True)
    n = a.parse_args(); open(n.o, 'wb').write(build(PRESETS[n.preset], n.serial)); print('wrote', n.o)
