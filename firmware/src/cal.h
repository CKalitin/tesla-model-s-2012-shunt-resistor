/* Calibration, kept in the last 1 KB flash page so it survives power cycles.
 *
 * mA = (raw * 100 - offset_c) * num / den
 *   offset_c  zero offset, in hundredths of a raw count
 *   num/den   true mA per hundredth of a count (default 1/100, i.e. raw counts = mA)
 */
#pragma once
#include <stdint.h>

typedef struct {
    uint32_t magic;
    int32_t offset_c;
    int32_t num;
    int32_t den;
} cal_t;

extern cal_t cal;

void cal_load(void);    /* from flash, or defaults if the page is blank */
int cal_save(void);     /* returns 0 on success */
void cal_defaults(void);
int32_t cal_apply(int64_t raw_c); /* raw in hundredths of a count -> mA */
