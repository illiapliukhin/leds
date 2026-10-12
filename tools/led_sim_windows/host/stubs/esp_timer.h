#pragma once
#include <stdint.h>
int64_t esp_timer_get_time(void);
typedef void *esp_timer_handle_t;
typedef enum { ESP_TIMER_TASK = 0 } esp_timer_dispatch_t;
typedef struct { void (*callback)(void *); void *arg; esp_timer_dispatch_t dispatch_method; const char *name; } esp_timer_create_args_t;
static inline int esp_timer_create(const esp_timer_create_args_t *a, esp_timer_handle_t *h) { (void)a; *h = 0; return 0; }
static inline int esp_timer_start_periodic(esp_timer_handle_t h, uint64_t p) { (void)h; (void)p; return 0; }
static inline int esp_timer_stop(esp_timer_handle_t h) { (void)h; return 0; }
