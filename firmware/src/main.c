/* Tesla Model S 2012 current shunt -> serial terminal.
 *
 * Streams the pack current over the ST-LINK virtual COM port (115200 8N1).
 * Type a command and press Enter (see help() below for the list).
 *
 * "raw" means the int32 the shunt sends in reply bytes 3..6. Reference code treats
 * it as mA, but on this 2012 shunt 3 A read about 60, so it goes through the
 * calibration in cal.c before being shown as amps.
 */
#include <stddef.h>
#include "board.h"
#include "cal.h"
#include "shunt.h"

static int streaming = 1;
static int raw_bytes = 0;
static uint32_t period_ms = 200;

/* ---------- printing ---------- */

static void print_milli(int32_t m) /* 1234 -> "1.234" */
{
    if (m < 0) { uart_putc('-'); m = -m; }
    uart_int(m / 1000);
    uart_putc('.');
    int32_t frac = m % 1000;
    uart_putc((char)('0' + frac / 100));
    uart_putc((char)('0' + frac / 10 % 10));
    uart_putc((char)('0' + frac % 10));
}

static void print_centi(int64_t c) /* 1234 -> "12.34" */
{
    if (c < 0) { uart_putc('-'); c = -c; }
    uart_int((int32_t)(c / 100));
    uart_putc('.');
    uart_putc((char)('0' + (int)(c / 10 % 10)));
    uart_putc((char)('0' + (int)(c % 10)));
}

static void print_bytes(const uint8_t *b, int n)
{
    for (int i = 0; i < n; i++) { uart_putc(' '); uart_hex8(b[i]); }
}

/* ---------- reading ---------- */

enum { READ_OK, READ_NO_REPLY, READ_ZEROS, READ_BAD };

/* One current read, checked: CRC must pass and the reply must echo 41. Replies are
 * one frame late, so the first read after any other command comes back READ_BAD. */
static int read_raw(int32_t *out, uint8_t *rx)
{
    int32_t v = shunt_read_ma(rx);
    int ff = 1, zero = 1;
    for (int i = 0; i < SHUNT_FRAME_LEN; i++) {
        if (rx[i] != 0xFF) ff = 0;
        if (rx[i] != 0x00) zero = 0;
    }
    if (ff) return READ_NO_REPLY;
    if (zero) return READ_ZEROS;
    if (shunt_crc8(rx, 7) != rx[7] || rx[0] != 0x41) return READ_BAD;
    *out = v;
    return READ_OK;
}

/* Average n good reads, 10 ms apart. Result in hundredths of a count. */
static int average_c(int n, int64_t *avg_c, int32_t *min, int32_t *max)
{
    uint8_t rx[SHUNT_FRAME_LEN];
    int64_t sum = 0;
    int got = 0, tries = 0;
    *min = 0x7FFFFFFF;
    *max = -0x7FFFFFFF;
    while (got < n) {
        if (++tries > n * 2 + 10) return -1;
        int32_t v;
        if (read_raw(&v, rx) == READ_OK) {
            sum += v;
            got++;
            if (v < *min) *min = v;
            if (v > *max) *max = v;
        }
        delay_ms(10);
    }
    *avg_c = sum * 100 / n;
    return 0;
}

static void sample(void)
{
    uint8_t rx[SHUNT_FRAME_LEN];
    int32_t v;

    switch (read_raw(&v, rx)) {
    case READ_NO_REPLY: uart_puts("no reply (MISO idle high: shunt not connected/powered?)\r\n"); return;
    case READ_ZEROS:    uart_puts("no reply (all zeros)\r\n"); return;
    case READ_BAD:
        if (raw_bytes) { uart_puts("skip (not a 41 reply):"); print_bytes(rx, SHUNT_FRAME_LEN); uart_puts("\r\n"); }
        return;
    }

    uart_puts("I = ");
    print_milli(cal_apply((int64_t)v * 100));
    uart_puts(" A  (raw ");
    uart_int(v);
    uart_puts(")");
    if (raw_bytes) { uart_puts("  rx:"); print_bytes(rx, SHUNT_FRAME_LEN); }
    uart_puts("\r\n");
}

/* ---------- commands ---------- */

static void help(void)
{
    uart_puts("\r\nTesla shunt reader. Commands (then Enter):\r\n"
              "  h          help\r\n"
              "  s          stream on/off\r\n"
              "  p <ms>     sample period\r\n"
              "  a [n]      average n readings (default 200, ~2 s)\r\n"
              "  z          zero: average with NO current flowing, save as offset\r\n"
              "  c <mA>     calibrate: with a known current flowing, give its true\r\n"
              "             value in mA (negative if reversed). Do z first.\r\n"
              "  c          show calibration\r\n"
              "  u          undo calibration and offset (back to raw counts)\r\n"
              "  r          raw bytes on/off\r\n"
              "  i          re-run init, print responses\r\n"
              "  x <hex..>  send a frame; <=7 bytes gets CRC-8 appended\r\n\r\n");
}

static void show_cal(void)
{
    uart_puts("offset = ");
    print_centi(cal.offset_c);
    uart_puts(" counts, scale = ");
    uart_int(cal.num);
    uart_puts(" mA per ");
    print_centi(cal.den);
    uart_puts(" counts\r\n");
}

static void save(void)
{
    uart_puts(cal_save() ? "FLASH WRITE FAILED\r\n" : "saved to flash\r\n");
}

static int parse_int(const char *s, int32_t *out)
{
    while (*s == ' ') s++;
    int neg = (*s == '-');
    if (neg || *s == '+') s++;
    if (*s < '0' || *s > '9') return -1;
    int32_t v = 0;
    while (*s >= '0' && *s <= '9') v = v * 10 + (*s++ - '0');
    *out = neg ? -v : v;
    return 0;
}

static void cmd_average(const char *arg)
{
    int32_t n = 200, mn, mx;
    int64_t avg_c;
    parse_int(arg, &n);
    if (n < 1 || n > 5000) { uart_puts("a <1..5000>\r\n"); return; }
    uart_puts("averaging...\r\n");
    if (average_c(n, &avg_c, &mn, &mx)) { uart_puts("too many bad replies\r\n"); return; }
    uart_puts("avg I = ");
    print_milli(cal_apply(avg_c));
    uart_puts(" A  (raw ");
    print_centi(avg_c);
    uart_puts(", min ");
    uart_int(mn);
    uart_puts(", max ");
    uart_int(mx);
    uart_puts(", n=");
    uart_int(n);
    uart_puts(")\r\n");
}

static void cmd_zero(void)
{
    int32_t mn, mx;
    int64_t avg_c;
    uart_puts("zeroing (no current!)...\r\n");
    if (average_c(200, &avg_c, &mn, &mx)) { uart_puts("too many bad replies\r\n"); return; }
    cal.offset_c = (int32_t)avg_c;
    show_cal();
    save();
}

static void cmd_cal(const char *arg)
{
    int32_t true_ma, mn, mx;
    int64_t avg_c;

    if (parse_int(arg, &true_ma)) { show_cal(); return; }
    if (true_ma == 0) { uart_puts("use z for zero, c <mA> for a non-zero current\r\n"); return; }

    uart_puts("calibrating, hold the current steady...\r\n");
    if (average_c(500, &avg_c, &mn, &mx)) { uart_puts("too many bad replies\r\n"); return; }
    int64_t span_c = avg_c - cal.offset_c;
    uart_puts("raw above zero = ");
    print_centi(span_c);
    uart_puts(" counts\r\n");
    if (span_c > -500 && span_c < 500) {
        uart_puts("under 5 counts: too small to calibrate, use more current\r\n");
        return;
    }
    cal.num = true_ma;
    cal.den = (int32_t)span_c;
    show_cal();
    uart_puts("1 count = ");
    print_milli((int32_t)((int64_t)true_ma * 100 * 1000 / span_c));
    uart_puts(" mA\r\n");
    save();
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
    case 'r': raw_bytes = !raw_bytes; uart_puts(raw_bytes ? "raw on\r\n" : "raw off\r\n"); break;
    case 'i': shunt_init(1); break;
    case 'x': cmd_frame(arg); break;
    case 'a': cmd_average(arg); break;
    case 'z': cmd_zero(); break;
    case 'c': cmd_cal(arg); break;
    case 'u': cal_defaults(); show_cal(); save(); break;
    case 'p': {
        int32_t v;
        if (parse_int(arg, &v) || v < 10 || v > 10000) { uart_puts("p <10..10000>\r\n"); break; }
        period_ms = (uint32_t)v;
        uart_puts("period = "); uart_int(v); uart_puts(" ms\r\n");
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
    cal_load();
    delay_ms(200); /* let the shunt's STM8 boot if both power up together */

    uart_puts("\r\n=== Tesla Model S shunt reader (STM32F031K6) ===\r\n");
    shunt_init(1);
    show_cal();
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
