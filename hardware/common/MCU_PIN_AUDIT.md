# ESP32-S3FN8 pin audit

Status: schematic baseline. Physical pin numbers were checked against the
ESP32-S3 QFN56 pin table; GPIO15/16 are physical pins 21/22 and GPIO47/48 are
physical pins 37/36. KiCad's stock symbol labels pins 21/22 as the optional
32 kHz crystal functions, but they retain GPIO15/16 capability.

| Physical pin | GPIO / supply | Assigned net | Reset requirement |
|---:|---|---|---|
| 2, 3 | VDD3P3 | AON_3V3 | Decouple locally |
| 4 | CHIP_PU | CHIP_PU | 10 kΩ up, 1 µF down |
| 6 | GPIO1 | MIC_ADC | High impedance |
| 7 | GPIO2 | BAT_TS_ADC | High impedance |
| 9 | GPIO4 | PCB_NTC_ADC | High impedance |
| 10 | GPIO5 | PCB_NTC_EXCITE | Low/off |
| 13 | GPIO8 | I2C_SDA | External pull-up |
| 14 | GPIO9 | I2C_SCL | External pull-up |
| 15 | GPIO10 | IMU_INT1 | Input, wake-capable |
| 16 | GPIO11 | BUTTON_WAKE_N | Input, wake-capable |
| 17 | GPIO12 | GAUGE_ALERT_N | Input |
| 18 | GPIO13 | MCU_LED_CLK | Pull-down |
| 19 | GPIO14 | MCU_LED_SDI | Pull-down |
| 21 | GPIO15 / XTAL_32K_P | MCU_LED_LE | Pull-down |
| 22 | GPIO16 / XTAL_32K_N | MCU_LED_OE_N | Pull-up |
| 23 | GPIO17 | ROW_A0 | Low |
| 24 | GPIO18 | ROW_A1 | Low |
| 25 | GPIO19 / USB_D− | USB_MCU_D_N | USB function |
| 26 | GPIO20 / USB_D+ | USB_MCU_D_P | USB function |
| 27 | GPIO21 | ROW_A2 | Low |
| 36 | GPIO48 / SPICLK_N | LED_SDO_RETURN | Input, external pull-down |
| 37 | GPIO47 / SPICLK_P | ROW_XLAT_OE_N | High / translator disabled |
| 38 | GPIO33 | ROW_A3 | Low |
| 39 | GPIO34 | DEC_A_EN_N | High / bank disabled |
| 40 | GPIO35 | DEC_B_EN_N | High / bank disabled |
| 41 | GPIO36 | LED_EN | Low |
| 42 | GPIO37 | AUDIO_EN | Low |
| 43 | GPIO38 | CHG_CE_N | Charger-safe default |
| 44 | GPIO39 / MTCK | CHG_STAT1_N | Input |
| 45 | GPIO40 / MTDO | CHG_STAT2_N | Input |
| 47 | GPIO41 / MTDI | CHG_SHIP_N | Inactive |
| 48 | GPIO42 / MTMS | LED_LOGIC_EN | Low |
| 49 | GPIO43 / U0TXD | SERVICE_UART_TX | UART |
| 50 | GPIO44 / U0RXD | SERVICE_UART_RX | UART |
| 53, 54 | XTAL_N/P | 40 MHz crystal | Dedicated |
| 55, 56 | VDDA | AON_3V3 | Filter/decouple per Espressif |
| 57 | GND / exposed pad | GND | Solid ground and thermal vias |

## Reserved and unavailable

- GPIO0, GPIO3, GPIO45, and GPIO46 remain unused because they are strapping
  pins.
- Physical pins 30–35 are consumed by the in-package Quad SPI flash on
  `ESP32-S3FN8`.
- RF pin 1 is unused because Wi-Fi/BLE are not enabled, but its required
  package/layout treatment must still follow the Espressif hardware guide.
- GPIO15/16 cannot be used for an external 32.768 kHz crystal in this design.

## Remaining validation

- Verify power-up GPIO glitch behavior in the selected ESP-IDF revision and
  keep hardware pulls authoritative.
- Confirm ADC attenuation/range for both NTC channels and the microphone.
- Review VDDA filtering, all decoupling, RF-pin treatment, 40 MHz crystal load,
  and CHIP_PU timing against the final layout.
- Confirm charger safe defaults and the exact `CHG_SHIP_N` implementation once
  the BQ25185 TS/MR and current-limit circuit is finalized.
