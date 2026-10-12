#pragma once
#include <stdint.h>
/* Full-8-bit generative patterns shared by the single-panel demos (demo.c) and the stack canvas (stack.c).
 * pattern_px returns 0..1 linear intensity (the scan engine applies gamma 2.2 to the 8-bit level). */
enum { PAT_VYSH = 0, PAT_AURORA, PAT_KINETIC, PAT_N };
float pattern_px(int pat, int X, int Y, int W, int H, float t);
