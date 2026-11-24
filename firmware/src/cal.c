#include "cal.h"
#include "stm32f031.h"

#define CAL_MAGIC 0x5A17CA11u
#define CAL_ADDR  0x08007C00u /* last 1 KB page; the linker script keeps code out of it */

cal_t cal;

void cal_defaults(void)
{
    cal.magic = CAL_MAGIC;
    cal.offset_c = 0;
    cal.num = 1;
    cal.den = 100;
}

void cal_load(void)
{
    const cal_t *stored = (const cal_t *)CAL_ADDR;
    if (stored->magic == CAL_MAGIC && stored->den != 0)
        cal = *stored;
    else
        cal_defaults();
}

int32_t cal_apply(int64_t raw_c)
{
    return (int32_t)((raw_c - cal.offset_c) * cal.num / cal.den);
}

static int flash_wait(void)
{
    while (FLASH_SR & FLASH_SR_BSY) {}
    uint32_t sr = FLASH_SR;
    FLASH_SR = FLASH_SR_EOP | FLASH_SR_PGERR | FLASH_SR_WRPRTERR; /* write-1-to-clear */
    return (sr & (FLASH_SR_PGERR | FLASH_SR_WRPRTERR)) ? -1 : 0;
}

int cal_save(void)
{
    int err = 0;

    FLASH_KEYR = 0x45670123u;
    FLASH_KEYR = 0xCDEF89ABu;

    FLASH_CR = FLASH_CR_PER;
    FLASH_AR = CAL_ADDR;
    FLASH_CR = FLASH_CR_PER | FLASH_CR_STRT;
    err |= flash_wait();

    FLASH_CR = FLASH_CR_PG;
    const uint16_t *src = (const uint16_t *)&cal;
    volatile uint16_t *dst = (volatile uint16_t *)CAL_ADDR;
    for (unsigned i = 0; i < sizeof cal / 2; i++) {
        dst[i] = src[i];
        err |= flash_wait();
    }

    FLASH_CR = FLASH_CR_LOCK;
    return err;
}
