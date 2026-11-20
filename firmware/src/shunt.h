/* Tesla Model S (2012) pack current shunt, SPI master side.
 *
 * Protocol from Tom deBree's Tesla-Current-Shunt Arduino sketch
 * (https://github.com/Tom-evnut/Tesla-Current-Shunt):
 *   SPI mode 0, MSB first, 8-bit, 500 kHz, active-low NSS around each frame.
 *   Frames are 8 bytes: command, 6 data bytes, then a check byte.
 *   The check byte is CRC-8 (poly 0x07, init 0x00, no reflection, no xorout);
 *   this was confirmed against all 7 known command frames.
 *   Command 0x41 returns current in mA as a little-endian int32 in rx bytes 3..6.
 */
#pragma once
#include <stdint.h>

#define SHUNT_FRAME_LEN 8

uint8_t shunt_crc8(const uint8_t *data, int len);

/* Clock out len bytes of tx with NSS held low, filling rx with what MISO returned. */
void shunt_transfer(const uint8_t *tx, uint8_t *rx, int len);

/* Send the 8-frame wake/config sequence. Every response is printed if verbose. */
void shunt_init(int verbose);

/* Read the current. rx (8 bytes) receives the raw response if non-null. */
int32_t shunt_read_ma(uint8_t *rx);
