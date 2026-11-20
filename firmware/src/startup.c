/* Cortex-M0 startup: vector table, .data/.bss init, then main(). */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern int main(void);
void SysTick_Handler(void);

void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata;) *dst++ = *src++;
    for (uint32_t *dst = &_sbss; dst < &_ebss;) *dst++ = 0;
    main();
    for (;;) {}
}

/* GCC may emit calls to these even in freestanding code (e.g. for `= {0}`),
 * and we link without libc. */
#include <stddef.h>
void *memset(void *dst, int c, size_t n)
{
    unsigned char *d = dst;
    while (n--) *d++ = (unsigned char)c;
    return dst;
}

void *memcpy(void *dst, const void *src, size_t n)
{
    unsigned char *d = dst;
    const unsigned char *s = src;
    while (n--) *d++ = *s++;
    return dst;
}

static void Default_Handler(void)
{
    for (;;) {}
}

/* The core vectors are all this firmware needs; peripheral IRQs stay unused. */
__attribute__((section(".isr_vector"), used))
const void *const vector_table[16] = {
    &_estack,
    Reset_Handler,
    Default_Handler, /* NMI */
    Default_Handler, /* HardFault */
    0, 0, 0, 0, 0, 0, 0,
    Default_Handler, /* SVC */
    0, 0,
    Default_Handler, /* PendSV */
    SysTick_Handler,
};
