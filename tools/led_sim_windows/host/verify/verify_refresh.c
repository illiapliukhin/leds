/* Bit-exact check of the simulator's duty LUT against the CURRENT firmware matrix_refresh.c:
 * the firmware file is #included verbatim (MONO_SIM path), its own compute_layout/build_gamma/
 * build_template/build_data produce the real 50 ns sample stream, which is decoded here (OE-low samples
 * while each LED's latched bit is 1) and compared with sim_duty_lut() from led_host.c. */
#include <stdio.h>
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
#define portENTER_CRITICAL_ISR(x) ((void)(x))
#define portEXIT_CRITICAL_ISR(x) ((void)(x))
#define portMUX_INITIALIZER_UNLOCKED 0
#define MONO_SIM 1
#include "matrix_refresh.c"
#undef TAG
void sim_duty_lut(int br, float gamma, float *out);
uint8_t matrix_panel_get_level(const matrix_panel_t *p, uint8_t r, uint8_t c) { (void)p; (void)r; (void)c; return 0; }
esp_err_t mbi5124_driver_init(void) { return ESP_OK; }
int main(void)
{
    compute_layout();
    printf("row %u samples, frame %u samples, %.1f Hz\n", s_row_samples, s_frame_samples, 1e9 / ((double)s_frame_samples * MATRIX_SAMPLE_NS));
    uint16_t *b = calloc(s_frame_samples, 2); int bad = 0; float lut[256];
    int brs[] = {1, 37, 128, 200, 255}; float gs[] = {1.0f, 2.2f, 2.8f};
    for (int gi = 0; gi < 3; gi++) for (int bi = 0; bi < 5; bi++) {
        s_gamma_val = gs[gi]; build_gamma(); s_brightness = brs[bi];
        sim_duty_lut(brs[bi], gs[gi], lut);
        for (int base = 0; base < 256; base += 32) {
            for (int r = 0; r < 32; r++) for (int c = 0; c < 32; c++) s_levels[r][c] = (uint8_t)(base + c);
            build_template(b); build_data(b);
            for (int c = 0; c < 32; c++) {
                /* decode row 0: shift register content latched at each LE, OE-low samples counted while bit set */
                uint32_t sr = 0, latched = 0, on = 0; uint16_t *p = b;
                for (uint32_t i = 0; i < s_row_samples; i++) {
                    sr = (sr << 1) | (p[i] & MBUS_SDI);
                    if (p[i] & MBUS_LE) latched = sr;
                    if (!(p[i] & MBUS_OE_N) && ((latched >> c) & 1)) on++;
                }
                float fw = on / 510.0f, sim = lut[base + c];
                if (fabsf(fw - sim) > 1e-6f) { if (bad < 5) printf("MISMATCH g %.1f br %d level %d: fw %.6f sim %.6f\n", gs[gi], brs[bi], base + c, fw, sim); bad++; }
            }
        }
    }
    printf("%s: %d mismatches over 3 gammas x 5 brightness x 256 levels\n", bad ? "FAIL" : "PASS", bad);
    return bad != 0;
}
