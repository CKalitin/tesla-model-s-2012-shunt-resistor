/* Board support for the NUCLEO-F031K6 (also fine on a bare STM32F031K6).
 *
 *   Signal      MCU pin  Nucleo pin   Shunt connector J1
 *   SPI1_SCK    PB3      D13          pin 4 SCK   (PB3 also drives the green LED LD3)
 *   SPI1_MISO   PB4      D12          pin 5 MISO
 *   SPI1_MOSI   PB5      D11          pin 6 MOSI
 *   NSS (GPIO)  PA11     D10          pin 3 NSS
 *   GND                  GND          pin 2 GND
 *   +5V                  5V           pin 1 VDD
 *   USART1_TX   PA2      (ST-LINK virtual COM port, 115200 8N1)
 *   USART1_RX   PA15     (ST-LINK virtual COM port)
 *
 * All four SPI pins are 5 V tolerant (FT), so the shunt's 5 V MISO is safe as long
 * as the STM32 is powered. Our 3.3 V outputs sit below the STM8's guaranteed
 * VIH (0.7 x 5 V = 3.5 V); see firmware/README.md if the shunt never answers.
 */
#pragma once
#include <stdint.h>

void board_init(void);
void board_cs(int level);
uint8_t spi_xfer(uint8_t b);

uint32_t millis(void);
void delay_ms(uint32_t ms);
void delay_us(uint32_t us);

void uart_putc(char c);
void uart_puts(const char *s);
void uart_hex8(uint8_t b);
void uart_int(int32_t v);
int uart_getc(void); /* -1 when nothing is waiting */
