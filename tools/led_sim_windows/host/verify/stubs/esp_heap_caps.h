#pragma once
#include <stdlib.h>
#define MALLOC_CAP_DMA 1
#define MALLOC_CAP_INTERNAL 2
static inline void *heap_caps_aligned_calloc(size_t a, size_t n, size_t s, int c) { (void)a; (void)c; return calloc(n, s); }
