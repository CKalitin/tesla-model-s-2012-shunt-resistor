#include "shunt.h"
#include "board.h"

uint8_t shunt_crc8(const uint8_t *data, int len)
{
    uint8_t crc = 0;
    while (len--) {
        crc ^= *data++;
        for (int i = 0; i < 8; i++)
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x07) : (uint8_t)(crc << 1);
    }
    return crc;
}

void shunt_transfer(const uint8_t *tx, uint8_t *rx, int len)
{
    board_cs(0);
    delay_us(10);
    for (int i = 0; i < len; i++) {
        uint8_t b = spi_xfer(tx[i]);
        if (rx) rx[i] = b;
    }
    delay_us(10);
    board_cs(1);
    delay_us(50);
}

/* Init sequence, byte for byte as in the reference sketch. The first frame is an
 * 11-byte oddity (looks like a wake-up/unlock); the rest are normal 8-byte frames. */
static const uint8_t init_wake[] = {0x7F, 0x7F, 0x21, 0xDE, 0x00, 0x00, 0x00, 0x80, 0x00, 0x80, 0x00};
static const uint8_t init_frames[][SHUNT_FRAME_LEN] = {
    {0x4F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xBC},
    {0x4E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x63},
    {0x4E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x63},
    {0x16, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x33},
    {0x14, 0x00, 0x00, 0xDC, 0x05, 0xC2, 0x01, 0x83},
    {0x13, 0x00, 0x00, 0x04, 0x01, 0x02, 0x08, 0x94},
    {0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xC0},
};

static void dump(const char *label, const uint8_t *tx, const uint8_t *rx, int len)
{
    uart_puts(label);
    uart_puts(" tx:");
    for (int i = 0; i < len; i++) { uart_putc(' '); uart_hex8(tx[i]); }
    uart_puts("\r\n      rx:");
    for (int i = 0; i < len; i++) { uart_putc(' '); uart_hex8(rx[i]); }
    uart_puts("\r\n");
}

void shunt_init(int verbose)
{
    uint8_t rx[sizeof init_wake];

    shunt_transfer(init_wake, rx, sizeof init_wake);
    if (verbose) dump("wake", init_wake, rx, sizeof init_wake);
    delay_ms(2);

    for (unsigned f = 0; f < sizeof init_frames / sizeof init_frames[0]; f++) {
        shunt_transfer(init_frames[f], rx, SHUNT_FRAME_LEN);
        if (verbose) dump("init", init_frames[f], rx, SHUNT_FRAME_LEN);
        delay_ms(2);
    }
}

int32_t shunt_read_ma(uint8_t *rx_out)
{
    static const uint8_t cmd[SHUNT_FRAME_LEN] = {0x41, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x9A};
    uint8_t rx[SHUNT_FRAME_LEN];

    shunt_transfer(cmd, rx, SHUNT_FRAME_LEN);
    if (rx_out)
        for (int i = 0; i < SHUNT_FRAME_LEN; i++) rx_out[i] = rx[i];

    return (int32_t)((uint32_t)rx[3] | ((uint32_t)rx[4] << 8) |
                     ((uint32_t)rx[5] << 16) | ((uint32_t)rx[6] << 24));
}
