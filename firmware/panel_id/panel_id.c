#include "panel_id.h"
#include <string.h>

uint16_t panel_id_crc16(const uint8_t *p, uint16_t n) {
    uint16_t c = 0xFFFF;
    while (n--) { c ^= (uint16_t)(*p++) << 8; for (int i = 0; i < 8; i++) c = (c & 0x8000) ? (c << 1) ^ 0x1021 : c << 1; }
    return c;
}

void panel_id_default(panel_id_t *o) {
    memset(o, 0, sizeof *o);
    o->magic = PANEL_ID_MAGIC; o->version = 1; o->rec_len = PANEL_ID_REC_LEN;
    o->panel_class = PANEL_FLAT; o->led_type = LED_WHITE; o->rows = 32; o->cols = 32;
    o->pitch_um = 4000; o->i_led_ua = 10000; o->i_row_ma = 320; o->vf_mv = 3000;
    o->mapping = MAP_IDENTITY; o->blank_ns = 2000; o->row_mask = o->col_mask = 0xFFFFFFFFu;
    strncpy(o->name, "default32", sizeof o->name);
}

bool panel_id_read(panel_i2c_read_fn rd, panel_id_t *out) {
    panel_id_t r;
    if (!rd || rd(PANEL_ID_I2C_ADDR, 0x00, (uint8_t *)&r, sizeof r) != 0) goto dflt;   /* no ACK: legacy panel */
    if (r.magic != PANEL_ID_MAGIC || r.version != 1 || r.rec_len != PANEL_ID_REC_LEN) goto dflt;
    if (panel_id_crc16((const uint8_t *)&r, 0x3E) != r.crc16) goto dflt;
    if (!r.rows || r.rows > 32 || !r.cols || r.cols > 64) goto dflt;
    if (!(r.flags & PANEL_FLAG_PARTIAL)) {
        r.row_mask = r.rows == 32 ? 0xFFFFFFFFu : ((1u << r.rows) - 1);
        r.col_mask = r.cols >= 32 ? 0xFFFFFFFFu : ((1u << r.cols) - 1);
    }
    *out = r;
    return true;
dflt:
    panel_id_default(out);
    return false;
}

bool panel_map(const panel_id_t *id, uint8_t x, uint8_t y, uint8_t *row, uint8_t *col) {
    uint8_t W = id->cols, H = id->rows, r, c;
    if (x >= W || y >= H) return false;
    switch (id->mapping) {
    case MAP_MIRROR_X:  r = y;         c = W - 1 - x; break;
    case MAP_MIRROR_Y:  r = H - 1 - y; c = x;         break;
    case MAP_ROT180:    r = H - 1 - y; c = W - 1 - x; break;
    case MAP_TRANSPOSE: r = x;         c = y;         if (r >= H || c >= W) return false; break;
    case MAP_SERPENTINE_COLS: r = (x & 1) ? H - 1 - y : y; c = x; break;
    case MAP_TABLE:     /* TODO: look up firmware LUT id->table_id */ return false;
    default:            r = y;         c = x;         break;
    }
    *row = r; *col = c;
    return true;
}
