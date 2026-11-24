/* Minimal register definitions for the STM32F031K6 (RM0360).
 * Only what this firmware touches, so the project has no CMSIS/HAL dependency. */
#pragma once
#include <stdint.h>

#define REG32(addr) (*(volatile uint32_t *)(addr))

/* ---- RCC ---- */
#define RCC_BASE      0x40021000u
#define RCC_AHBENR    REG32(RCC_BASE + 0x14)
#define RCC_APB2ENR   REG32(RCC_BASE + 0x18)
#define RCC_AHBENR_IOPAEN    (1u << 17)
#define RCC_AHBENR_IOPBEN    (1u << 18)
#define RCC_APB2ENR_SPI1EN   (1u << 12)
#define RCC_APB2ENR_USART1EN (1u << 14)

/* ---- GPIO ---- */
typedef struct {
    volatile uint32_t MODER, OTYPER, OSPEEDR, PUPDR, IDR, ODR, BSRR, LCKR, AFR[2], BRR;
} GPIO_TypeDef;
#define GPIOA ((GPIO_TypeDef *)0x48000000u)
#define GPIOB ((GPIO_TypeDef *)0x48000400u)

/* ---- USART1 ---- */
typedef struct {
    volatile uint32_t CR1, CR2, CR3, BRR, GTPR, RTOR, RQR, ISR, ICR, RDR, TDR;
} USART_TypeDef;
#define USART1 ((USART_TypeDef *)0x40013800u)
#define USART_CR1_UE   (1u << 0)
#define USART_CR1_RE   (1u << 2)
#define USART_CR1_TE   (1u << 3)
#define USART_ISR_ORE  (1u << 3)
#define USART_ISR_RXNE (1u << 5)
#define USART_ISR_TXE  (1u << 7)
#define USART_ICR_ORECF (1u << 3)

/* ---- SPI1 ---- */
typedef struct {
    volatile uint32_t CR1, CR2, SR, DR;
} SPI_TypeDef;
#define SPI1 ((SPI_TypeDef *)0x40013000u)
#define SPI_CR1_MSTR  (1u << 2)
#define SPI_CR1_BR_DIV16 (3u << 3)
#define SPI_CR1_SPE   (1u << 6)
#define SPI_CR1_SSI   (1u << 8)
#define SPI_CR1_SSM   (1u << 9)
#define SPI_CR2_DS_8BIT (7u << 8)
#define SPI_CR2_FRXTH (1u << 12)
#define SPI_SR_RXNE   (1u << 0)
#define SPI_SR_TXE    (1u << 1)
#define SPI_SR_BSY    (1u << 7)
/* The F0 SPI packs two bytes into one 16-bit DR write, so 8-bit frames
 * must be written and read with byte-wide accesses. */
#define SPI1_DR8 (*(volatile uint8_t *)&SPI1->DR)

/* ---- Flash interface ---- */
#define FLASH_BASE_R  0x40022000u
#define FLASH_KEYR    REG32(FLASH_BASE_R + 0x04)
#define FLASH_SR      REG32(FLASH_BASE_R + 0x0C)
#define FLASH_CR      REG32(FLASH_BASE_R + 0x10)
#define FLASH_AR      REG32(FLASH_BASE_R + 0x14)
#define FLASH_SR_BSY      (1u << 0)
#define FLASH_SR_PGERR    (1u << 2)
#define FLASH_SR_WRPRTERR (1u << 4)
#define FLASH_SR_EOP      (1u << 5)
#define FLASH_CR_PG   (1u << 0)
#define FLASH_CR_PER  (1u << 1)
#define FLASH_CR_STRT (1u << 6)
#define FLASH_CR_LOCK (1u << 7)

/* ---- SysTick ---- */
#define SYST_CSR REG32(0xE000E010u)
#define SYST_RVR REG32(0xE000E014u)
#define SYST_CVR REG32(0xE000E018u)
