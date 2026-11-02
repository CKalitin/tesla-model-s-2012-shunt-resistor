#!/usr/bin/env python3
"""Draw every IC pin, part, test pad and via onto the board photo.

Positions come from parts.csv / vias.csv (board-photo pixel coordinates in the 3024x4032
image embedded in annotations/board/Traces-and-pins.pdf). Output:
annotations/board/netlist_overlay.jpg
"""
import csv, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'annotations', 'board')
OUT = os.path.join(BOARD, 'netlist_overlay.jpg')
OX, OY, X1, Y1 = 640, 820, 2200, 3090
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def board_image():
    """Extract the raw photo (object 12) from the background PDF with mutool."""
    raw = os.path.join(tempfile.gettempdir(), 'shunt_board.rgb')
    with open(raw, 'wb') as f:
        subprocess.run(['mutool', 'show', '-b', os.path.join(BOARD, 'Traces-and-pins.pdf'), '12'], stdout=f, check=True)
    return Image.frombytes('RGB', (3024, 4032), open(raw, 'rb').read())


im = board_image().crop((OX, OY, X1, Y1))
d = ImageDraw.Draw(im, 'RGBA')
F = ImageFont.truetype(BOLD, 22)
Fs = ImageFont.truetype(BOLD, 16)
Fp = ImageFont.truetype(BOLD, 13)


def P(x, y):
    return (x - OX, y - OY)


def lab(x, y, t, c, f=Fs, center=False):
    X, Y = P(x, y)
    bb = d.textbbox((X, Y), t, font=f)
    if center:
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        X, Y = X - w / 2, Y - h / 2
        bb = d.textbbox((X, Y), t, font=f)
    d.rectangle((bb[0] - 2, bb[1] - 1, bb[2] + 2, bb[3] + 1), fill=(0, 0, 0, 175))
    d.text((X, Y), t, fill=c, font=f)


def line(pts, c, w=5):
    d.line([P(*p) for p in pts], fill=c, width=w, joint='curve')


# traces actually seen in the photos
G = (60, 255, 60, 210)
for pts in [[(1120, 1300), (1032, 1279), (944, 1300)], [(1120, 1347), (870, 1349), (840, 1380)],
            [(1120, 1396), (948, 1398), (930, 1466)], [(1120, 1442), (1046, 1453)],
            [(1120, 1490), (1040, 1505), (990, 1574)], [(1120, 1586), (1077, 1587)],
            [(1645, 1376), (1760, 1370), (1782, 1261)],
            [(1082, 2165), (1060, 2075), (1110, 2008), (1394, 2010)],
            [(1250, 2775), (1290, 2874)], [(1174, 2775), (1141, 2881)], [(1021, 2775), (900, 2850), (818, 2891)]]:
    line(pts, G)
for x in (2125, 2140, 2155):
    line([(x, 1000), (x, 2900)], (255, 200, 0, 170), 3)

# parts
for p in csv.DictReader(open(os.path.join(HERE, 'parts.csv'))):
    x, y = int(p['board_x']), int(p['board_y'])
    if p['kind'] in ('STM8AF6266TC', 'IHM-A-1500', 'LM2903'):
        lab(x, y, f'{p["ref"]} {p["value"]}', '#ffffff', F, center=True)
    elif p['kind'] in ('CONN8', 'SHUNT'):
        continue
    elif p['kind'] == 'TP':
        d.rectangle((P(x, y)[0] - 30, P(x, y)[1] - 30, P(x, y)[0] + 30, P(x, y)[1] + 30), outline='#ffff00', width=3)
        lab(x, y, p['ref'], '#ffff40', Fs, center=True)
    else:
        X, Y = P(x, y)
        d.rectangle((X - 23, Y - 23, X + 23, Y + 23), outline='#ff40ff', width=3)
        v = '' if p['value'].startswith('C?') else ' ' + p['value']
        lab(x + 26, y - 12, p['ref'] + v, '#ffb0ff')

# vias
for v in csv.DictReader(open(os.path.join(HERE, 'vias.csv'))):
    x, y = int(v['board_x']), int(v['board_y'])
    X, Y = P(x, y)
    d.ellipse((X - 20, Y - 20, X + 20, Y + 20), outline='#ff8800', width=3)
    lab(x + 14, y + 12, v['id'], '#ffa040', Fp)

# IC pins
PWR = {'VDD', 'VDDIO', 'VDDA', 'VCAP', 'VDDD', 'VCC'}
GNDS = {'VSS', 'VSSA', 'VSSD', 'GND', 'AGND'}


def col(t):
    b = t.split()[1].split('/')[0]
    return '#ffe040' if b in PWR else ('#c8c8c8' if b in GNDS else '#60ffff')


def plab(x, y, t, anchor, rot=False):
    c = col(t)
    tb = d.textbbox((0, 0), t, font=Fp)
    w, h = tb[2] - tb[0] + 6, tb[3] - tb[1] + 6
    L = Image.new('RGBA', (w, h), (0, 0, 0, 190))
    ImageDraw.Draw(L).text((3, 3 - tb[1]), t, fill=c, font=Fp)
    if rot:
        L = L.rotate(90, expand=True)
        w, h = L.size
    X, Y = P(x, y)
    X, Y = {'r': (X, Y - h / 2), 'l': (X - w, Y - h / 2), 'u': (X - w / 2, Y - h), 'd': (X - w / 2, Y)}[anchor]
    im.paste(L, (int(X), int(Y)), L)
    d.ellipse((P(x, y)[0] - 3, P(x, y)[1] - 3, P(x, y)[0] + 3, P(x, y)[1] + 3), fill=c)


u1 = {'bot': ['1 NRST', '2 PA1/OSCIN', '3 PA2/OSCOUT', '4 VSS', '5 VCAP', '6 VDD', '7 VDDIO', '8 PF4/AIN12'],
      'right': ['9 VDDA', '10 VSSA', '11 PB5/AIN5/SDA', '12 PB4/AIN4/SCL', '13 PB3/AIN3', '14 PB2/AIN2', '15 PB1/AIN1', '16 PB0/AIN0'],
      'top': ['17 PE5/NSS', '18 PC1/T1CH1', '19 PC2/T1CH2', '20 PC3/T1CH3', '21 PC4/T1CH4', '22 PC5/SCK', '23 PC6/MOSI', '24 PC7/MISO'],
      'left': ['25 PD0/T3CH2/CCO', '26 PD1/SWIM', '27 PD2/T3CH1', '28 PD3/T2CH2', '29 PD4/T2CH1', '30 PD5/UART_TX', '31 PD6/UART_RX', '32 PD7/TLI']}
for i, t in enumerate(u1['bot']):
    plab(1250 + i * 47.6, 1745, t, 'd', rot=True)
for i, t in enumerate(u1['right']):
    plab(1680, 1612 - i * 47, t, 'r')
for i, t in enumerate(u1['top']):
    plab(1569 - i * 47.9, 1165, t, 'u', rot=True)
for i, t in enumerate(u1['left']):
    plab(1105, 1298 + i * 47, t, 'l')
for x, t in zip([1310, 1230, 1158, 1080, 1001, 925, 850, 775],
                ['1 RSHL', '2 RSHH', '3 ETS', '4 VBAT', '5 VSS', '6 EZPRG', '7 VSSD', '8 CLK']):
    plab(x, 2150, t, 'u', rot=True)
for x, t in zip([793, 869, 945, 1021, 1098, 1174, 1250, 1331],
                ['9 SCLK', '10 SDAT', '11 INTN', '12 VDDD', '13 VDDA', '14 REF', '15 AGND', '16 ETR']):
    plab(x, 2800, t, 'd', rot=True)
for x, t in zip([2106, 2028, 1950, 1867], ['1 OUT1', '2 1IN-', '3 1IN+', '4 GND']):
    plab(x, 1895, t, 'u', rot=True)
for x, t in zip([1880, 1954, 2028, 2102], ['5 2IN+', '6 2IN-', '7 OUT2', '8 VCC']):
    plab(x, 2345, t, 'd', rot=True)

lab(2080, 1300, 'edge bus', '#ffd000')
im.save(OUT, quality=92)
print('wrote', OUT, im.size)
