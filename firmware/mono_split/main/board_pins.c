#include "board_pins.h"

#define BOARD_PIN_ROW(gpio_num, pad, net, role) \
    { (gpio_num), (pad), (net), (role) },

const board_pin_entry_t board_pin_table[] = {
    BOARD_PIN_TABLE(BOARD_PIN_ROW)
};

const size_t board_pin_table_count = sizeof(board_pin_table) / sizeof(board_pin_table[0]);
