/* Clocking: the default 8 MHz HSI with no PLL. That gives an exact 500 kHz
 * SPI clock (8 MHz / 16) and 115200 baud to within 0.6 %. */
#include "board.h"
#include "stm32f031.h"

#define F_CPU 8000000u

static volatile uint32_t ms_ticks;

void SysTick_Handler(void) { ms_ticks++; }

uint32_t millis(void) { return ms_ticks; }

void delay_ms(uint32_t ms)
{
    uint32_t start = ms_ticks;
    while (ms_ticks - start < ms) {}
}

/* For short waits (< 1 ms) using the SysTick down-counter. */
void delay_us(uint32_t us)
{
    const uint32_t reload = SYST_RVR + 1;
    uint32_t want = us * (F_CPU / 1000000u);
    uint32_t last = SYST_CVR, elapsed = 0;
    while (elapsed < want) {
        uint32_t now = SYST_CVR;
        elapsed += (last >= now) ? (last - now) : (last + reload - now);
        last = now;
    }
}

static void pin_mode(GPIO_TypeDef *port, int pin, uint32_t mode, uint32_t af)
{
    port->MODER = (port->MODER & ~(3u << (pin * 2))) | (mode << (pin * 2));
    volatile uint32_t *afr = &port->AFR[pin >> 3];
    int shift = (pin & 7) * 4;
    *afr = (*afr & ~(0xFu << shift)) | (af << shift);
}

#define MODE_OUT 1u
#define MODE_AF  2u

void board_init(void)
{
    RCC_AHBENR |= RCC_AHBENR_IOPAEN | RCC_AHBENR_IOPBEN;
    RCC_APB2ENR |= RCC_APB2ENR_SPI1EN | RCC_APB2ENR_USART1EN;

    /* 1 ms SysTick on the core clock */
    SYST_RVR = F_CPU / 1000u - 1;
    SYST_CVR = 0;
    SYST_CSR = 7;

    /* USART1 on PA2 (TX) / PA15 (RX), AF1: the ST-LINK virtual COM port */
    pin_mode(GPIOA, 2, MODE_AF, 1);
    pin_mode(GPIOA, 15, MODE_AF, 1);
    GPIOA->PUPDR |= 1u << (15 * 2); /* pull-up on RX */
    USART1->BRR = (F_CPU + 115200u / 2) / 115200u;
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;

    /* NSS on PA11, idle high */
    GPIOA->BSRR = 1u << 11;
    pin_mode(GPIOA, 11, MODE_OUT, 0);

    /* SPI1 on PB3 (SCK) / PB4 (MISO) / PB5 (MOSI), AF0 */
    pin_mode(GPIOB, 3, MODE_AF, 0);
    pin_mode(GPIOB, 4, MODE_AF, 0);
    pin_mode(GPIOB, 5, MODE_AF, 0);
    GPIOB->PUPDR |= 1u << (4 * 2); /* pull-up on MISO so an absent shunt reads FF, not noise */

#ifdef SHUNT_OPEN_DRAIN
    /* Open-drain outputs for external pull-ups to the shunt's 5 V (see README).
     * Needs LD3 removed (open SB on the Nucleo) or SCK moved off PB3. */
    GPIOB->OTYPER |= (1u << 3) | (1u << 5);
    GPIOA->OTYPER |= 1u << 11;
#endif

    /* Master, mode 0 (CPOL=0, CPHA=0), MSB first, f/16 = 500 kHz, software NSS */
    SPI1->CR1 = SPI_CR1_MSTR | SPI_CR1_BR_DIV16 | SPI_CR1_SSM | SPI_CR1_SSI;
    SPI1->CR2 = SPI_CR2_DS_8BIT | SPI_CR2_FRXTH; /* RXNE fires on each byte */
    SPI1->CR1 |= SPI_CR1_SPE;
}

void board_cs(int level)
{
    GPIOA->BSRR = level ? (1u << 11) : (1u << (11 + 16));
}

uint8_t spi_xfer(uint8_t b)
{
    while (!(SPI1->SR & SPI_SR_TXE)) {}
    SPI1_DR8 = b;
    while (!(SPI1->SR & SPI_SR_RXNE)) {}
    uint8_t r = SPI1_DR8;
    while (SPI1->SR & SPI_SR_BSY) {}
    return r;
}

void uart_putc(char c)
{
    while (!(USART1->ISR & USART_ISR_TXE)) {}
    USART1->TDR = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s) uart_putc(*s++);
}

void uart_hex8(uint8_t b)
{
    static const char hex[] = "0123456789ABCDEF";
    uart_putc(hex[b >> 4]);
    uart_putc(hex[b & 15]);
}

void uart_int(int32_t v)
{
    char buf[12];
    int i = 0;
    uint32_t u = v < 0 ? 0u - (uint32_t)v : (uint32_t)v;
    if (v < 0) uart_putc('-');
    do { buf[i++] = (char)('0' + u % 10); u /= 10; } while (u);
    while (i) uart_putc(buf[--i]);
}

int uart_getc(void)
{
    uint32_t isr = USART1->ISR;
    if (isr & USART_ISR_ORE) USART1->ICR = USART_ICR_ORECF;
    if (!(isr & USART_ISR_RXNE)) return -1;
    return (int)(USART1->RDR & 0xFF);
}
