idf_component_register(
    SRCS
        "main.c"
        "board_pins.c"
        "power_seq.c"
        "mbi5124_driver.c"
        "matrix_panel.c"
        "matrix_refresh.c"
        "bmi270_probe.c"
        "test_patterns.c"
        "console_test.c"
        "demo.c"
        "sim_scan.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_timer esp_driver_gpio esp_driver_spi esp_driver_i2c console nvs_flash esp_hw_support esp_lcd
)

if(MONO_SIM)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE MONO_SIM=1)
endif()
