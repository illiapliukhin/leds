#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t power_seq_init(void);
esp_err_t power_seq_matrix_enable(void);
esp_err_t power_seq_matrix_disable(void);

#ifdef __cplusplus
}
#endif
