"""Parser for the v13 sim tap: '@G' lines = one decoded LCD_CAM frame (8-bit BCM)."""
FULL_SLOTS = [2 << k for k in range(8)]          # full-scale OE samples per plane (brightness 255)

def parse_g(line):
    p = line.split()
    if len(p) < 18 + 32 or p[0] != '@G':
        return None
    h = {'seq': int(p[1]), 'fps_obs': int(p[2]) / 10, 'fps_nom': int(p[3]) / 10, 'gen': int(p[4]), 'sample_ns': int(p[5]),
         'row_samples': int(p[6]), 'build_cycles': int(p[7]), 'bright': int(p[8]), 'gamma': int(p[9]) / 100}
    slots = [int(x) for x in p[10:18]]
    rows = []
    for tok in p[18:18 + 32]:
        parts = tok.split(':')
        drow = int(parts[0]); words = [int(w, 16) for w in parts[1].split(',')]
        on = [int(x) for x in parts[2].split(',')] if len(parts) > 2 else slots
        rows.append((drow, list(zip(words, on))))
    h['slots'] = slots; h['rows'] = rows
    return h

def full_scale_duty(row_samples):
    return sum(FULL_SLOTS) / row_samples

# HW CPU estimate for the scan path (ESP32-S3 @ 240 MHz, cycles counted from the build loops):
#   frame build (SDI bits only, template cached): 8192 RMW x ~6 cyc + 1024 gamma lookups x ~4 = ~53 k cyc
#   per-frame DMA hand-off (esp_lcd tx_color + trans-done ISR + task switch): ~5 k cyc
def hw_cpu_pct(fps_content=60, fps_scan=960):
    return 100.0 * (fps_content * 53e3 + fps_scan * 5e3) / 240e6
