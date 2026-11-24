# Regenerate the wiring diagram: python3 docs/gen_pinout.py docs/nucleo-wiring.svg
import sys

OUT = sys.argv[1]

# NUCLEO-F031K6 headers (UM1956), USB at the top, pin 1 at the top of each header.
CN3 = [("D1", "PA9"), ("D0", "PA10"), ("NRST", ""), ("GND", ""), ("D2", "PA12"),
       ("D3", "PB0"), ("D4", "PB7"), ("D5", "PB6"), ("D6", "PB1"), ("D7", "PF0"),
       ("D8", "PF1"), ("D9", "PA8"), ("D10", "PA11"), ("D11", "PB5"), ("D12", "PB4")]
CN4 = [("VIN", ""), ("GND", ""), ("NRST", ""), ("+5V", ""), ("A7", "PA2"),
       ("A6", "PA7"), ("A5", "PA6"), ("A4", "PA5"), ("A3", "PA4"), ("A2", "PA3"),
       ("A1", "PA1"), ("A0", "PA0"), ("AREF", ""), ("+3V3", ""), ("D13", "PB3")]

COL = {"VDD": "#d62728", "GND": "#222222", "NSS": "#ff7f0e",
       "SCK": "#c9a400", "MISO": "#2ca02c", "MOSI": "#1f77b4"}

# (header, index) -> (J1 pin, signal, note)
USED = {
    ("CN4", 3): (1, "VDD", "+5 V to shunt"),
    ("CN4", 1): (2, "GND", "ground"),
    ("CN3", 12): (3, "NSS", "SPI chip select (GPIO)"),
    ("CN4", 14): (4, "SCK", "SPI1_SCK · also LED LD3"),
    ("CN3", 14): (5, "MISO", "SPI1_MISO"),
    ("CN3", 13): (6, "MOSI", "SPI1_MOSI"),
}
NOTES = {("CN4", 4): "VCP TX (serial, in use)"}

W, H = 1180, 815
BX0, BX1, BY0, BY1 = 420, 640, 70, 715
PY0, DY = 130, 37
LPX, RPX = BX0 + 22, BX1 - 22

s = []
a = s.append
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
  'font-family="DejaVu Sans, Arial, sans-serif">')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
a('<text x="30" y="40" font-size="22" font-weight="bold" fill="#111">NUCLEO-F031K6 → Tesla Model S shunt (J1)</text>')

# board
a(f'<rect x="{BX0}" y="{BY0}" width="{BX1-BX0}" height="{BY1-BY0}" rx="10" fill="#f4f6f8" stroke="#555" stroke-width="2"/>')
a(f'<rect x="{(BX0+BX1)/2-38}" y="{BY0-22}" width="76" height="40" rx="4" fill="#c8ccd0" stroke="#555" stroke-width="2"/>')
a(f'<text x="{(BX0+BX1)/2}" y="{BY0+4}" font-size="12" text-anchor="middle" fill="#333">USB</text>')
a(f'<text x="{(BX0+BX1)/2}" y="{BY1-12}" font-size="11" text-anchor="middle" fill="#888">NUCLEO-F031K6 (top view)</text>')
a(f'<text x="{LPX}" y="{BY0+38}" font-size="12" fill="#666">CN3</text>')
a(f'<text x="{RPX}" y="{BY0+38}" font-size="12" text-anchor="end" fill="#666">CN4</text>')

def pin(header, i, name, mcu):
    y = PY0 + i * DY + 20
    left = header == "CN3"
    px = LPX if left else RPX
    used = USED.get((header, i))
    color = COL[used[1]] if used else "#7a7f85"
    a(f'<circle cx="{px}" cy="{y}" r="8" fill="{color if used else "#d9dcdf"}" stroke="{color}" stroke-width="2.5"/>')
    # name inside the board
    tx = px + 16 if left else px - 16
    anchor = "start" if left else "end"
    weight = "bold" if used else "normal"
    a(f'<text x="{tx}" y="{y+4}" font-size="13" font-weight="{weight}" text-anchor="{anchor}" fill="#111">{name}</text>')
    if mcu:
        mx = tx + (44 if left else -44)
        a(f'<text x="{mx}" y="{y+4}" font-size="11" text-anchor="{anchor}" fill="#666">{mcu}</text>')
    if used:
        jp, sig, note = used
        if left:
            x1, x2 = BX0 - 160, BX0 - 8
            a(f'<line x1="{x2}" y1="{y}" x2="{px-8}" y2="{y}" stroke="{color}" stroke-width="3"/>')
            a(f'<rect x="{x1}" y="{y-14}" width="{x2-x1}" height="28" rx="14" fill="{color}"/>')
            a(f'<text x="{(x1+x2)/2}" y="{y+5}" font-size="13" font-weight="bold" text-anchor="middle" fill="#fff">J1-{jp}  {sig}</text>')
            a(f'<text x="{x1-10}" y="{y+4}" font-size="12" text-anchor="end" fill="#444">{note}</text>')
        else:
            x1, x2 = BX1 + 8, BX1 + 160
            a(f'<line x1="{px+8}" y1="{y}" x2="{x1}" y2="{y}" stroke="{color}" stroke-width="3"/>')
            a(f'<rect x="{x1}" y="{y-14}" width="{x2-x1}" height="28" rx="14" fill="{color}"/>')
            a(f'<text x="{(x1+x2)/2}" y="{y+5}" font-size="13" font-weight="bold" text-anchor="middle" fill="#fff">J1-{jp}  {sig}</text>')
            a(f'<text x="{x2+10}" y="{y+4}" font-size="12" fill="#444">{note}</text>')
    elif (header, i) in NOTES:
        a(f'<text x="{BX1+10}" y="{y+4}" font-size="11" font-style="italic" fill="#888">{NOTES[(header, i)]}</text>')

for i, (n, m) in enumerate(CN3):
    pin("CN3", i, n, m)
for i, (n, m) in enumerate(CN4):
    pin("CN4", i, n, m)

# J1 connector panel (bottom left)
J = [(1, "VDD", "+5V"), (2, "GND", "GND"), (3, "NSS", "D10"), (4, "SCK", "D13"),
     (5, "MISO", "D12"), (6, "MOSI", "D11"), (7, "OC_FLAG", "not connected"), (8, "PC4", "not connected")]
jx, jy = 920, 330
a(f'<rect x="{jx}" y="{jy}" width="230" height="{40 + len(J)*30}" rx="8" fill="#fafafa" stroke="#555" stroke-width="2"/>')
a(f'<text x="{jx+12}" y="{jy+26}" font-size="15" font-weight="bold" fill="#111">Shunt connector J1</text>')
for k, (n, sig, to) in enumerate(J):
    y = jy + 52 + k * 30
    c = COL.get(sig, "#bbbbbb")
    a(f'<rect x="{jx+12}" y="{y-11}" width="22" height="22" rx="3" fill="{c}"/>')
    a(f'<text x="{jx+23}" y="{y+5}" font-size="12" font-weight="bold" text-anchor="middle" fill="#fff">{n}</text>')
    a(f'<text x="{jx+44}" y="{y+5}" font-size="13" font-weight="bold" fill="#111">{sig}</text>')
    a(f'<text x="{jx+130}" y="{y+5}" font-size="12" fill="#555">→ {to}</text>')

# notes
notes = [
    "SPI mode 0 · 500 kHz · 3.3 V logic works (no level shifter needed)",
    "Serial: ST-LINK virtual COM port, 115200 8N1 (USART1 on PA2 / PA15)",
    "Bench use only: J1 GND is the HV bus bar. Never wire to a live pack without isolation.",
]
for k, t in enumerate(notes):
    weight = "bold" if k == 2 else "normal"
    fill = "#b00020" if k == 2 else "#333"
    a(f'<text x="30" y="{H-62+k*22}" font-size="13" font-weight="{weight}" fill="{fill}">{t}</text>')

a('</svg>')
open(OUT, "w").write("\n".join(s))
print("wrote", OUT)
