/* Tesla Model S 2012 current shunt -> serial terminal.
 *
 * Streams the pack current over the ST-LINK virtual COM port (115200 8N1).
 * Type a command and press Enter:
 *   h            help
 *   s            stream on/off
 *   p <ms>       sample period (10..10000 ms)
 *   r            raw mode on/off (also prints the 8 response bytes)
 *   z            zero: use the current reading as the offset (z again clears it)
 *   i            re-send the init sequence and print every response
 *   x <bytes..>  send one frame of hex bytes and print the response.
 *                Give up to 7 bytes and the CRC-8 is appended for you
 *                (e.g. "x 41" reads current); give 8 to send them verbatim.
 */
#include <stddef.h>
#include "board.h"
#include "shunt.h"

static int streaming = 1;
static int raw = 0;
static uint32_t period_ms = 200;
static int32_t offset_ma = 0;

static void print_amps(int32_t ma)
{
    if (ma < 0) { uart_putc('-'); ma = -ma; }
    uart_int(ma / 1000);
    uart_putc('.');
    int32_t frac = ma % 1000;
    uart_putc((char)('0' + frac / 100));
    uart_putc((char)('0' + frac / 10 % 10));
    uart_putc((char)('0' + frac % 10));
}

static void print_bytes(const uint8_t *b, int n)
{
    for (int i = 0; i < n; i++) { uart_putc(' '); uart_hex8(b[i]); }
}

static void sample(void)
{
    uint8_t rx[SHUNT_FRAME_LEN];
    int32_t ma = shunt_read_ma(rx) - offset_ma;

    /* An undriven MISO reads all FF (our pull-up) or all 00; that's not a reading. */
    int ff = 1, zero = 1;
    for (int i = 0; i < SHUNT_FRAME_LEN; i++) {
        if (rx[i] != 0xFF) ff = 0;
        if (rx[i] != 0x00) zero = 0;
    }
    if (ff || zero) {
        uart_puts(ff ? "no reply (MISO idle high: shunt not connected/powered?)\r\n"
                     : "no reply (all zeros)\r\n");
        return;
    }
    /* The reply answers the previous frame, so it must echo 0x41 and pass its CRC.
     * The first read after init (or after an x command) fails this and is skipped. */
    if (shunt_crc8(rx, 7) != rx[7] || rx[0] != 0x41) {
        if (raw) { uart_puts("skip (not a 41 reply):"); print_bytes(rx, SHUNT_FRAME_LEN); uart_puts("\r\n"); }
        return;
    }

    uart_puts("I = ");
    print_amps(ma);
    uart_puts(" A  (");
    uart_int(ma);
    uart_puts(" mA)");
    if (raw) {
        uart_puts("  rx:");
        print_bytes(rx, SHUNT_FRAME_LEN);
    }
    uart_puts("\r\n");
}

static void help(void)
{
    uart_puts("\r\nTesla shunt reader. Commands (then Enter):\r\n"
              "  h          help\r\n"
              "  s          stream on/off\r\n"
              "  p <ms>     sample period\r\n"
              "  r          raw bytes on/off\r\n"
              "  z          zero offset (again to clear)\r\n"
              "  i          re-run init, print responses\r\n"
              "  x <hex..>  send a frame; <=7 bytes gets CRC-8 appended\r\n\r\n");
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static void cmd_frame(const char *s)
{
    uint8_t tx[SHUNT_FRAME_LEN] = {0}, rx[SHUNT_FRAME_LEN];
    int n = 0;

    while (*s) {
        while (*s == ' ' || *s == ',') s++;
        if (!*s) break;
        if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
        int hi = hexval(s[0]), lo = hexval(s[1]);
        if (hi < 0) { uart_puts("bad hex\r\n"); return; }
        if (n == SHUNT_FRAME_LEN) { uart_puts("max 8 bytes\r\n"); return; }
        if (lo < 0) { tx[n++] = (uint8_t)hi; s += 1; }
        else        { tx[n++] = (uint8_t)(hi << 4 | lo); s += 2; }
    }
    if (n == 0) { uart_puts("usage: x 41   or   x 41 00 00 00 00 00 00 9A\r\n"); return; }
    if (n < SHUNT_FRAME_LEN) tx[7] = shunt_crc8(tx, 7);

    /* The shunt answers each frame during the *next* one, so follow up with a
     * harmless current read (41) and print what comes back during it. */
    static const uint8_t flush[SHUNT_FRAME_LEN] = {0x41, 0, 0, 0, 0, 0, 0, 0x9A};
    shunt_transfer(tx, NULL, SHUNT_FRAME_LEN);
    delay_ms(2);
    shunt_transfer(flush, rx, SHUNT_FRAME_LEN);

    uart_puts("tx:");
    print_bytes(tx, SHUNT_FRAME_LEN);
    uart_puts("\r\nrx:");
    print_bytes(rx, SHUNT_FRAME_LEN);
    uart_puts(shunt_crc8(rx, 7) == rx[7] ? "  crc ok" : "  CRC BAD");
    if (rx[0] != tx[0]) uart_puts("  (echo mismatch)");
    uart_puts("\r\n   data (bytes 3..6, LE int32): ");
    uart_int((int32_t)((uint32_t)rx[3] | (uint32_t)rx[4] << 8 |
                       (uint32_t)rx[5] << 16 | (uint32_t)rx[6] << 24));
    uart_puts("\r\n");
}

static void run_command(char *line)
{
    while (*line == ' ') line++;
    char c = line[0];
    const char *arg = line[0] ? line + 1 : line;

    switch (c) {
    case 0: break;
    case 'h': case '?': help(); break;
    case 's': streaming = !streaming; uart_puts(streaming ? "stream on\r\n" : "stream off\r\n"); break;
    case 'r': raw = !raw; uart_puts(raw ? "raw on\r\n" : "raw off\r\n"); break;
    case 'i': shunt_init(1); break;
    case 'x': cmd_frame(arg); break;
    case 'z':
        if (offset_ma) { offset_ma = 0; uart_puts("offset cleared\r\n"); }
        else {
            offset_ma = shunt_read_ma(NULL);
            uart_puts("offset = "); uart_int(offset_ma); uart_puts(" mA\r\n");
        }
        break;
    case 'p': {
        uint32_t v = 0;
        while (*arg == ' ') arg++;
        while (*arg >= '0' && *arg <= '9') v = v * 10 + (uint32_t)(*arg++ - '0');
        if (v < 10 || v > 10000) { uart_puts("p <10..10000>\r\n"); break; }
        period_ms = v;
        uart_puts("period = "); uart_int((int32_t)v); uart_puts(" ms\r\n");
        break;
    }
    default: uart_puts("? (h for help)\r\n"); break;
    }
}

int main(void)
{
    char line[48];
    unsigned len = 0;

    board_init();
    delay_ms(200); /* let the shunt's STM8 boot if both power up together */

    uart_puts("\r\n=== Tesla Model S shunt reader (STM32F031K6) ===\r\n");
    shunt_init(1);
    help();

    uint32_t next = millis();
    for (;;) {
        int ch = uart_getc();
        if (ch == '\r' || ch == '\n') {
            if (len) uart_puts("\r\n");
            line[len] = 0;
            run_command(line);
            len = 0;
        } else if (ch == 0x7F || ch == 0x08) {
            if (len) { len--; uart_puts("\b \b"); }
        } else if (ch >= ' ' && len < sizeof line - 1) {
            line[len++] = (char)ch;
            uart_putc((char)ch); /* echo */
        }

        /* Hold the stream while a command is being typed so the echo stays readable. */
        if (streaming && len == 0 && (int32_t)(millis() - next) >= 0) {
            next += period_ms;
            if ((int32_t)(millis() - next) > 0) next = millis() + period_ms;
            sample();
        }
    }
}
