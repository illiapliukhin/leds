/* Panel ID EEPROM (LED_INTERFACE_STANDARD v1) - stub, not yet linked into mono_split.
 * Record lives at 0x00 of a 24C02-class EEPROM, I2C 7-bit address 0x50, reached
 * through J_ROW1 pins 35 (ID_SDA) / 36 (ID_SCL) / 37 (ID_3V3). Little-endian. */
#pragma once
#include <stdint.h>
#include <stdbool.h>

#define PANEL_ID_I2C_ADDR   0x50
#define PANEL_ID_MAGIC      0x5044454Cu /* "LEDP" */
#define PANEL_ID_REC_LEN    64

typedef enum { PANEL_FLAT = 0, PANEL_LATTICE = 1, PANEL_FULL_BLEED = 2, PANEL_GARLAND = 3,
               PANEL_BREAKOUT_ONLY = 4, PANEL_COL_EXPANSION = 5 } panel_class_t;
typedef enum { LED_WHITE = 0, LED_RED = 1, LED_GREEN = 2, LED_BLUE = 3, LED_AMBER = 4,
               LED_WARM_WHITE = 5 } led_type_t;
/* mapping: logical (x right, y down) -> physical (row, col) on the FFC lines */
typedef enum { MAP_IDENTITY = 0, MAP_MIRROR_X = 1, MAP_MIRROR_Y = 2, MAP_ROT180 = 3,
               MAP_TRANSPOSE = 4, MAP_SERPENTINE_COLS = 5, MAP_TABLE = 0x80 } panel_map_t;

#define PANEL_FLAG_VLED_SENSE   (1u << 0) /* pin 34 carries a panel-end VLED sense */
#define PANEL_FLAG_LONG_WIRES   (1u << 1) /* use pre-discharge + blank_ns from record */
#define PANEL_FLAG_PARTIAL      (1u << 2) /* row/col masks valid (freeform nets)    */

typedef struct __attribute__((packed)) {
    uint32_t magic;          /* 0x00 "LEDP" */
    uint8_t  version;        /* 0x04 = 1 */
    uint8_t  rec_len;        /* 0x05 = 64 */
    uint8_t  panel_class;    /* 0x06 panel_class_t */
    uint8_t  led_type;       /* 0x07 led_type_t */
    uint8_t  rows;           /* 0x08 1..32 lines used on J_ROW */
    uint8_t  cols;           /* 0x09 1..32 (64 with column expansion) */
    uint16_t pitch_um;       /* 0x0A 0 = freeform */
    uint16_t i_led_ua;       /* 0x0C max peak current per LED (sets brightness cap) */
    uint16_t i_row_ma;       /* 0x0E max row current the panel/wires accept */
    uint16_t vf_mv;          /* 0x10 typical LED Vf at i_led */
    uint8_t  mapping;        /* 0x12 panel_map_t */
    uint8_t  flags;          /* 0x13 PANEL_FLAG_* */
    uint16_t blank_ns;       /* 0x14 min blanking around a row change */
    uint16_t predischarge_ns;/* 0x16 all-sinks-on slot with no row selected, 0 = off */
    uint16_t row_path_mohm;  /* 0x18 cable + net row resistance estimate */
    uint16_t hw_rev;         /* 0x1A */
    uint32_t serial;         /* 0x1C */
    char     name[16];       /* 0x20 NUL-padded ASCII, e.g. "mono32_flat" */
    uint32_t row_mask;       /* 0x30 populated rows (bit0 = ROW_01), valid with PARTIAL */
    uint32_t col_mask;       /* 0x34 populated cols */
    uint16_t table_id;       /* 0x38 firmware built-in LUT id when mapping == MAP_TABLE */
    uint8_t  reserved[4];    /* 0x3A */
    uint16_t crc16;          /* 0x3E CRC-16/CCITT-FALSE over 0x00..0x3D */
} panel_id_t;
_Static_assert(sizeof(panel_id_t) == PANEL_ID_REC_LEN, "panel_id_t size");

/* Board-specific I2C read: fills buf from EEPROM word address `addr`. Return 0 on ACK. */
typedef int (*panel_i2c_read_fn)(uint8_t dev7, uint8_t addr, uint8_t *buf, uint16_t len);

uint16_t panel_id_crc16(const uint8_t *p, uint16_t n);
/* Probe + validate. On any failure fills *out with the default profile and returns false. */
bool panel_id_read(panel_i2c_read_fn rd, panel_id_t *out);
void panel_id_default(panel_id_t *out);       /* mono_panel_32x32 flat, white, 10 mA */
/* Logical pixel -> physical line indices (0-based). Returns false if outside panel. */
bool panel_map(const panel_id_t *id, uint8_t x, uint8_t y, uint8_t *row, uint8_t *col);
