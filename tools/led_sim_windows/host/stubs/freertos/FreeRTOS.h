#pragma once
#include <stdint.h>
typedef uint32_t TickType_t;
typedef int BaseType_t;
typedef void *TaskHandle_t;
typedef void *SemaphoreHandle_t;
typedef int portMUX_TYPE;
#define pdTRUE 1
#define pdFALSE 0
#define pdPASS 1
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms))
#define portMAX_DELAY 0xFFFFFFFFu
#define configMAX_PRIORITIES 25
#define IRAM_ATTR
#define portYIELD_FROM_ISR(x) ((void)(x))
static inline int xPortInIsrContext(void) { return 0; }
