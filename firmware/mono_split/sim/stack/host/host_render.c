/* Host build of the firmware showcase demos: the SAME patterns.c the boards run, driven by a fixed simulated
 * clock (frame n at t = n / fps), quantised exactly like stack.c render_tile (8-bit level) and mapped through the
 * firmware's gamma LUT (matrix_refresh.c build_gamma, gamma 2.2) -> BCM code per LED.
 * Output: raw frames, W*H bytes each (BCM code 0..255, duty = code/255 of full scale), no drops, no repeats.
 * usage: host_render <pattern 0..2> <W> <H> <fps> <t0_s> <n_frames> > frames.raw */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "patterns.h"
int main(int argc, char **argv)
{
    if (argc < 7) { fprintf(stderr, "usage\n"); return 1; }
    int pat = atoi(argv[1]), W = atoi(argv[2]), H = atoi(argv[3]), fps = atoi(argv[4]);
    double t0 = atof(argv[5]); long n = atol(argv[6]);
    uint8_t gam[256];
    for (int i = 0; i < 256; i++) { float v = powf(i / 255.0f, 2.2f) * 255.0f + 0.5f; gam[i] = (uint8_t)(v > 255 ? 255 : v); }
    uint8_t *buf = malloc((size_t)W * H);
    for (long f = 0; f < n; f++) {
        float t = (float)(t0 + (double)f / fps);
        for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
            float v = pattern_px(pat, x, y, W, H, t);
            int q = (int)(v * 255 + 0.5f); q = q > 255 ? 255 : q < 0 ? 0 : q;
            buf[y * W + x] = gam[q];
        }
        fwrite(buf, 1, (size_t)W * H, stdout);
    }
    return 0;
}
