#pragma once
#include "FreeRTOS.h"
/* Tasks are never started in the host build: the simulator drives the firmware's pure functions
 * (render, render_tile, canvas_px, compute_grid, crc8) directly; the stack state machine is
 * reproduced message-for-message by the Python bus model. */
static inline BaseType_t xTaskCreatePinnedToCore(void (*f)(void *), const char *n, int s, void *a, int p, TaskHandle_t *h, int c)
{ (void)f; (void)n; (void)s; (void)a; (void)p; (void)c; if (h) *h = 0; return pdPASS; }
static inline void vTaskDelay(TickType_t t) { (void)t; }
static inline void vTaskDelayUntil(TickType_t *w, TickType_t t) { *w += t; }
static inline TickType_t xTaskGetTickCount(void) { return 0; }
static inline void vTaskDelete(TaskHandle_t t) { (void)t; }
static inline uint32_t ulTaskNotifyTake(BaseType_t c, TickType_t t) { (void)c; (void)t; return 0; }
static inline void xTaskNotifyGive(TaskHandle_t t) { (void)t; }
static inline void vTaskNotifyGiveFromISR(TaskHandle_t t, BaseType_t *h) { (void)t; (void)h; }
