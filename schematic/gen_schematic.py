#!/usr/bin/env python3
"""Generate the KiCad schematic from parts.csv / connections.csv / measurements.csv.

The drawing is laid out by hand, block by block (draw_* functions): the shunt input filter, the IHM,
the MCU, the harness connector, SWIM/reset, and the comparator. Pull-ups, pull-downs and decoupling
caps sit on their pins; other connections use wires within a block and net labels between blocks.
Parts with no measured nets yet, and all test pads, sit in grids with labels.

Nets always come from connections.csv. Before writing, Sheet.verify() checks the drawing's own
connectivity against the CSV; afterwards check_with_kicad() compares KiCad's exported netlist.
Orange labels mark inferred nets and red labels unknown ones.

Usage:  python3 gen_schematic.py   (writes shunt.kicad_sch/.kicad_sym and build/shunt.pdf)
"""
import csv, math, os, re, subprocess, sys, uuid
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = 'shunt'
LIB = 'shunt'

# ---------------------------------------------------------------- symbol definitions
# Each IC: list of (number, name) for left side and right side, top to bottom.
SYMBOLS = {
    # Pin order is chosen for the drawing: each side faces the block it talks to.  None = empty row.
    'STM8AF6266TC': dict(half_w=27.94, left=[
        ('28', 'PD3/TIM2_CH2/ADC_ETR'), ('25', 'PD0/TIM3_CH2/CLK_CCO'), ('27', 'PD2/TIM3_CH1'),
        ('29', 'PD4/TIM2_CH1/BEEP'), None,
        ('2', 'PA1/OSCIN'), ('3', 'PA2/OSCOUT'), ('19', 'PC2/TIM1_CH2'), ('31', 'PD6/UART_RX'), ('32', 'PD7/TLI'), None,
        ('8', 'PF4/AIN12'), ('16', 'PB0/AIN0'), ('15', 'PB1/AIN1'), ('13', 'PB3/AIN3'), ('12', 'PB4/AIN4/I2C_SCL')],
        right=[
        ('14', 'PB2/AIN2'), ('17', 'PE5/SPI_NSS'), ('22', 'PC5/SPI_SCK'), ('24', 'PC7/SPI_MISO'),
        ('23', 'PC6/SPI_MOSI'), ('21', 'PC4/TIM1_CH4'), None, ('26', 'PD1/SWIM'), ('1', 'NRST'), None,
        ('11', 'PB5/AIN5/I2C_SDA'), ('18', 'PC1/TIM1_CH1'), ('20', 'PC3/TIM1_CH3'), ('30', 'PD5/UART_TX')],
        top=[('6', 'VDD'), ('7', 'VDDIO'), ('9', 'VDDA')],
        bottom=[('4', 'VSS'), ('10', 'VSSA'), ('5', 'VCAP')]),
    'IHM-A-1500': dict(half_w=15.24, rows=7, left=[
        ('2', 'RSHH'), ('1', 'RSHL'), ('4', 'VBAT'), ('3', 'ETS'), ('16', 'ETR')],
        right=[('10', 'SDAT'), ('8', 'CLK'), ('9', 'SCLK'), ('11', 'INTN')],
        top=[('13', 'VDDA'), ('12', 'VDDD'), ('6', 'EZPRG')],
        bottom=[('5', 'VSS'), ('7', 'VSSD'), ('14', 'REF'), ('15', 'AGND')]),
    'CONN8': dict(half_w=5.08, left=[('1', 'VDD'), ('2', 'VSS'), ('7', 'PIN7'), ('3', 'NSS'), ('4', 'SCK'),
                                      ('5', 'MISO'), ('6', 'MOSI'), ('8', 'PIN8')], right=[]),
    'SHUNT': dict(half_w=7.62, left=[('1', 'A')], right=[('2', 'B')]),
}
PITCH = 2.54
STUB = 2.54
COL = {'measured': (0, 132, 0), 'seen': (0, 132, 0), 'datasheet': (0, 132, 0),
       'inferred': (230, 120, 0), 'unknown': (210, 0, 0)}
RANK = {'measured': 0, 'seen': 1, 'datasheet': 2, 'inferred': 3, 'unknown': 4}


def U():
    return str(uuid.uuid4())


def fnt(size=1.27, color=None, bold=False, hide=False, justify=None):
    s = f'(effects (font (size {size} {size})'
    if bold:
        s += ' (bold yes)'
    if color:
        s += f' (color {color[0]} {color[1]} {color[2]} 1)'
    s += ')'
    if justify:
        s += f' (justify {justify})'
    if hide:
        s += ' (hide yes)'
    return s + ')'


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


# ---------------------------------------------------------------- library symbols
def ic_symbol(kind):
    d = SYMBOLS[kind]
    n = max(len(d['left']), len(d['right']), d.get('rows', 0))
    hh = round((n + 1) * PITCH / 2 / 1.27) * 1.27
    w = d['half_w']
    pins = []  # (number, name, x, y, angle) in lib coords (y up)
    for side, lst in (('L', d['left']), ('R', d['right'])):
        for i, pin in enumerate(lst):
            if pin is None:
                continue
            num, name = pin
            y = hh - PITCH * (i + 1)
            pins.append((num, name, -w - PITCH, y, 0) if side == 'L' else (num, name, w + PITCH, y, 180))
    for side, lst in (('T', d.get('top', [])), ('B', d.get('bottom', []))):
        for i, (num, name) in enumerate(lst):
            x = round((i - (len(lst) - 1) / 2) * 5.08, 2)
            pins.append((num, name, x, hh + PITCH, 270) if side == 'T' else (num, name, x, -hh - PITCH, 90))
    body = f'(rectangle (start {-w} {hh}) (end {w} {-hh}) (stroke (width 0.254) (type default)) (fill (type background)))'
    return pins, body, hh


def two_pin_symbol(kind):
    # horizontal: pin 1 left, pin 2 right; connection points at +-5.08
    pins = [('1', '~', -5.08, 0, 0), ('2', '~', 5.08, 0, 180)]
    if kind == 'R':
        body = '(rectangle (start -2.54 1.016) (end 2.54 -1.016) (stroke (width 0.254) (type default)) (fill (type none)))'
    elif kind == 'C':
        body = ('(polyline (pts (xy -0.508 1.524) (xy -0.508 -1.524)) (stroke (width 0.3) (type default)) (fill (type none)))'
                '(polyline (pts (xy 0.508 1.524) (xy 0.508 -1.524)) (stroke (width 0.3) (type default)) (fill (type none)))'
                '(polyline (pts (xy -2.54 0) (xy -0.508 0)) (stroke (width 0) (type default)) (fill (type none)))'
                '(polyline (pts (xy 0.508 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))')
    else:  # D: unknown-polarity diode drawn as a box with a bar
        body = ('(rectangle (start -2.54 1.016) (end 2.54 -1.016) (stroke (width 0.254) (type default)) (fill (type none)))'
                '(polyline (pts (xy 1.27 1.016) (xy 1.27 -1.016)) (stroke (width 0.254) (type default)) (fill (type none)))')
    return pins, body, 1.27


def tp_symbol():
    pins = [('1', '~', -2.54, 0, 0)]
    body = '(circle (center 0.762 0) (radius 0.762) (stroke (width 0.254) (type default)) (fill (type none)))'
    return pins, body, 1.27


def geometry(kind):
    if kind in SYMBOLS:
        return ic_symbol(kind)
    if kind in ('R', 'C', 'D'):
        return two_pin_symbol(kind)
    if kind == 'TP':
        return tp_symbol()
    raise KeyError(kind)


def lib_symbol(kind, prefix=''):
    pins, body, hh = geometry(kind)
    ic = kind in SYMBOLS
    hide_names = '' if ic else '(hide yes)'
    hide_nums = '' if kind not in ('TP',) else '(hide yes)'
    ref_prefix = {'STM8AF6266TC': 'U', 'IHM-A-1500': 'U', 'LM2903': 'U', 'CONN8': 'J', 'SHUNT': 'RS',
                  'R': 'R', 'C': 'C', 'D': 'D', 'TP': 'TP'}[kind]
    out = [f'(symbol {q(prefix + kind)} (pin_numbers {hide_nums}) (pin_names (offset 0.762) {hide_names})',
           '(exclude_from_sim no) (in_bom yes) (on_board yes)',
           f'(property "Reference" {q(ref_prefix)} (at 0 {hh + 1.27} 0) {fnt()})',
           f'(property "Value" {q(kind)} (at 0 {-hh - 1.27} 0) {fnt()})',
           f'(property "Footprint" "" (at 0 0 0) {fnt(hide=True)})',
           f'(property "Datasheet" "" (at 0 0 0) {fnt(hide=True)})',
           f'(property "Description" "" (at 0 0 0) {fnt(hide=True)})',
           f'(symbol {q(kind + "_0_1")} {body})',
           f'(symbol {q(kind + "_1_1")}']
    for num, name, x, y, ang in pins:
        ln = PITCH if ic else (2.54 if kind != 'TP' else 1.778)
        out.append(f'(pin passive line (at {x} {y} {ang}) (length {ln}) (name {q(name)} {fnt()}) (number {q(num)} {fnt()}))')
    out.append(')) ')
    return '\n'.join(out)


# ---------------------------------------------------------------- load data
def load():
    parts = list(csv.DictReader(open(os.path.join(HERE, 'parts.csv'))))
    conns = list(csv.DictReader(open(os.path.join(HERE, 'connections.csv'))))
    meas = list(csv.DictReader(open(os.path.join(HERE, 'measurements.csv'))))
    return parts, conns, meas


def resolve(parts, conns):
    """Return {(ref,pin): (net, status, note)} with placeholder nets for unknown pins."""
    byref = {p['ref']: p for p in parts}
    m = {}
    errs = []
    for c in conns:
        k = (c['ref'], c['pin'])
        if c['ref'] not in byref:
            errs.append(f'connections.csv: unknown ref {c["ref"]}')
            continue
        if k in m:
            errs.append(f'connections.csv: duplicate row for {k}')
        st = c['status'].strip()
        if st not in RANK:
            errs.append(f'connections.csv: bad status {st!r} for {k}')
        net = c['net'].strip() or f'?{c["ref"]}.{c["pin"]}'
        if st == 'unknown' and c['net'].strip() == '':
            pass
        m[k] = (net, st, c['note'])
    for p in parts:
        for num in lib_pins(lib_id_of(p['kind'])):
            if (p['ref'], num) not in m:
                errs.append(f'connections.csv: missing row for {p["ref"]} pin {num}')
    return m, errs


NOTES = [
    'HOW TO READ: every pin carries a net label; identical label text = same net.',
    'Green = measured / seen / datasheet.  Orange = inferred.  Red ?REF.PIN = destination unknown.',
    'Passive pin 1 = top pad (vertical parts) or left pad (horizontal parts) in Traces-and-pins.jpeg.',
    '',
    'SHUNT: board GND (and IHM RSHL, VBAT) is bonded to the bar. IHM RSHH sees the other end through a',
    '2-pole RC filter (R14 820R + C14, then R15 820R + C13).',
    'U3 = bidirectional overcurrent window. Each +IN = bar tap via 220R, offset toward +5V: +IN1 by R7 1M || R6 33.2k,',
    '+IN2 by R13 33.2k (~+33 mV) with R12 1M from OC_FLAG as hysteresis. Each -IN = bar tap via R10 820R / R9 220R. Wired-OR =',
    'OC_FLAG (active low): connector PIN7 + MCU PB2, 2.7k pull-up R5. Trips at ~34 mV across the shunt.',
    'IHM is powered from MCU GPIOs U1.2/3/19/31/32 (switchable). ETS/ETR unused. Connector PIN8 = U1.21 (PC4).',
]


# ---------------------------------------------------------------- drawing
# Standard KiCad symbols used instead of the generated ones.
STD_SYMBOLS = {'R': ('Device', 'R'), 'C': ('Device', 'C'), 'LM2903': ('Comparator', 'LM2903')}
KICAD_SYM_DIR = '/usr/share/kicad/symbols'
_LIBCACHE = {}


def kicad_symbol(lib, name):
    """Copy a symbol definition out of KiCad's stock library, renamed lib:name for lib_symbols."""
    key = (lib, name)
    if key not in _LIBCACHE:
        src = open(os.path.join(KICAD_SYM_DIR, f'{lib}.kicad_sym')).read()
        i = src.index(f'(symbol "{name}"\n')
        depth, j = 0, i
        while True:
            if src[j] == '(':
                depth += 1
            elif src[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        blk = src[i:j + 1].replace('(embedded_fonts no)', '')
        _LIBCACHE[key] = blk.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
    return _LIBCACHE[key]


def lib_pins(lib_id):
    """{pin: (x, y, angle, unit)} in library coordinates."""
    if lib_id.startswith(LIB + ':'):
        kind = lib_id.split(':', 1)[1]
        return {num: (x, y, ang, 1) for num, _, x, y, ang in geometry(kind)[0]}
    lib, name = lib_id.split(':')
    blk = kicad_symbol(lib, name)
    res = {}
    for m in re.finditer(r'\(symbol "' + re.escape(name) + r'_(\d+)_\d+"(.*?)(?=\(symbol "' + re.escape(name) + r'_\d+_\d+"|\Z)', blk, re.S):
        unit = int(m.group(1))
        for p in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(number "([^"]+)"', m.group(2), re.S):
            res[p.group(4)] = (float(p.group(1)), float(p.group(2)), int(p.group(3)), unit if unit else 1)
    return res


def lib_id_of(kind):
    if kind in STD_SYMBOLS:
        return '%s:%s' % STD_SYMBOLS[kind]
    return f'{LIB}:{kind}'


def rot_vec(sx, sy, rot):
    for _ in range((rot // 90) % 4):
        sx, sy = sy, -sx
    return sx, sy


def xf(lx, ly, rot):
    """Library point -> schematic offset for a symbol placed at angle `rot` (CCW)."""
    return rot_vec(lx, -ly, rot)


def P(x, y):
    return (round(x, 2), round(y, 2))


def flip_just(just, rot):
    """KiCad mirrors field justification on symbols turned 90 or 180 degrees."""
    if rot in (90, 180):
        return just.replace('left', 'TMP').replace('right', 'left').replace('TMP', 'right')
    return just


class Sheet:
    """Collects symbols, wires, labels and power symbols; checks connectivity before writing."""

    def __init__(self, root, parts, net_of):
        self.root, self.net_of = root, net_of
        self.byref = {p['ref']: p for p in parts}
        self.syms, self.segs, self.labels, self.powers, self.texts = [], [], [], [], []
        self.pin_at = {}       # (ref, pin) -> point
        self.pin_out = {}      # (ref, pin) -> outward unit vector
        self.placed_units = defaultdict(set)

    # ----- placement
    def place(self, ref, x, y, rot=0, unit=1, ref_at=None, val_at=None, just='', fields='right'):
        p = self.byref[ref]
        lib_id = lib_id_of(p['kind'])
        x, y = P(x, y)
        pins = lib_pins(lib_id)
        for num, (lx, ly, ang, u) in pins.items():
            if u not in (unit, 0) and not (lib_id.startswith(LIB) and True):
                continue
            if u != unit and not lib_id.startswith(LIB):
                continue
            dx, dy = xf(lx, ly, rot)
            self.pin_at[(ref, num)] = P(x + dx, y + dy)
            ix, iy = rot_vec(round(math.cos(math.radians(ang))), -round(math.sin(math.radians(ang))), rot)
            self.pin_out[(ref, num)] = (-ix, -iy)
        if ref_at is None:
            if fields == 'right':
                ref_at, val_at, just = (x + 2.54, y - 0.635), (x + 2.54, y + 1.905), 'left'
            elif fields == 'left':
                ref_at, val_at, just = (x - 2.54, y - 0.635), (x - 2.54, y + 1.905), 'right'
            elif fields == 'above':
                ref_at, val_at, just = (x, y - 3.3), (x, y + 3.3), ''
            elif fields == 'above2':
                ref_at, val_at, just = (x - 3.3, y - 2.03), (x + 2.79, y - 2.03), ''
            elif fields == 'below2':
                ref_at, val_at, just = (x - 3.3, y + 3.3), (x + 2.79, y + 3.3), ''
        self.syms.append(dict(ref=ref, lib_id=lib_id, x=x, y=y, rot=rot, unit=unit, ref_at=P(*ref_at),
                              val_at=P(*val_at), just=just, pins=[n for n, v in pins.items()
                                                                     if (v[3] == unit or lib_id.startswith(LIB))]))
        self.placed_units[ref].add(unit)
        return {n: self.pin_at[(ref, n)] for n in self.syms[-1]['pins']}

    def two(self, ref, x, y, axis, a_net, fields=None):
        """Place a 2-pin part centred on (x, y), 'v' or 'h', with the pin on net a_net at the top/left.
        Returns (a_point, b_point)."""
        kind = self.byref[ref]['kind']
        std = kind in STD_SYMBOLS                     # Device:R/C are vertical at rot 0, pin 1 on top
        if std:
            rots = (0, 180) if axis == 'v' else (90, 270)
        else:                                          # generated symbols are horizontal, pin 1 left
            rots = (270, 90) if axis == 'v' else (0, 180)
        n1 = self.net_of[(ref, '1')][0]
        rot = rots[0] if n1 == a_net else rots[1]
        if fields is None:
            fields = 'right' if axis == 'v' else 'above'
        pins = self.place(ref, x, y, rot, fields=fields)
        pa, pb = pins['1'], pins['2']
        if (axis == 'v' and pa[1] > pb[1]) or (axis == 'h' and pa[0] > pb[0]):
            pa, pb = pb, pa
        return pa, pb

    def pin(self, ref, num):
        return self.pin_at[(ref, num)]

    # ----- drawing primitives
    def wire(self, *pts):
        pts = [P(*p) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a != b:
                assert a[0] == b[0] or a[1] == b[1], f'diagonal wire {a} {b}'
                self.segs.append((a, b))

    def label(self, net, p, direction):
        self.labels.append((net, P(*p), direction))

    def power(self, net, p, direction):
        self.powers.append((net, P(*p), direction))

    def end(self, net, p, direction):
        if net in ('+5V', 'GND'):
            self.power(net, p, direction)
        else:
            self.label(net, p, direction)

    def text(self, t, x, y, size=2.0, bold=True):
        self.texts.append((t, P(x, y), size, bold))

    def stub(self, ref, num, length=2.54, net=None):
        """Short wire out of a pin, terminated by its net's label or power symbol."""
        p = self.pin(ref, num)
        ox, oy = self.pin_out[(ref, num)]
        e = P(p[0] + ox * length, p[1] + oy * length)
        self.wire(p, e)
        d = {(-1, 0): 'L', (1, 0): 'R', (0, -1): 'U', (0, 1): 'D'}[(ox, oy)]
        self.end(net or self.net_of[(ref, num)][0], e, d)
        return e

    # ----- finishing
    def finish(self):
        # every pin that nothing touches gets a stub + label
        touched = {pt for s in self.segs for pt in s} | {p for _, p, _ in self.labels} | {p for _, p, _ in self.powers}

        def on_wire(t):
            return any((a[0] == b[0] == t[0] and min(a[1], b[1]) <= t[1] <= max(a[1], b[1])) or
                       (a[1] == b[1] == t[1] and min(a[0], b[0]) <= t[0] <= max(a[0], b[0])) for a, b in self.segs)
        for (ref, num), pt in list(self.pin_at.items()):
            if pt not in touched and not on_wire(pt):
                self.stub(ref, num)
        # split wires wherever another item's connection point lands inside them
        terms = {pt for s in self.segs for pt in s} | set(self.pin_at.values()) | \
                {p for _, p, _ in self.labels} | {p for _, p, _ in self.powers}
        out = []
        for a, b in self.segs:
            inner = [t for t in terms if t not in (a, b) and (
                (a[0] == b[0] == t[0] and min(a[1], b[1]) < t[1] < max(a[1], b[1])) or
                (a[1] == b[1] == t[1] and min(a[0], b[0]) < t[0] < max(a[0], b[0])))]
            pts = sorted([a, b] + inner, key=lambda t: (t[0] - a[0]) ** 2 + (t[1] - a[1]) ** 2)
            out += list(zip(pts, pts[1:]))
        self.segs = out
        deg = defaultdict(int)
        for a, b in self.segs:
            deg[a] += 1
            deg[b] += 1
        for pt in self.pin_at.values():
            if pt in deg:
                deg[pt] += 1
        self.junctions = [pt for pt, n in deg.items() if n >= 3]
        self.verify()

    def verify(self):
        """Union-find over the drawing; every pin must land on its CSV net, and every net needs a name."""
        parent = {}

        def f(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def u(a, b):
            parent[f(a)] = f(b)

        for a, b in self.segs:
            u(a, b)
        for net, p, _ in self.labels + self.powers:
            u(('name', net), p)
        comp_pins = defaultdict(list)
        for k, pt in self.pin_at.items():
            comp_pins[f(pt)].append(k)
        names = defaultdict(set)
        for net, p, _ in self.labels + self.powers:
            names[f(p)].add(net)
        errs = []
        net_comps = defaultdict(set)
        for c, ks in comp_pins.items():
            want = {self.net_of[k][0] for k in ks}
            have = names.get(c, set())
            if len(want) != 1:
                errs.append(f'{sorted(ks)} joins nets {want}')
            elif have and have != want:
                errs.append(f'{sorted(ks)} on {want} drawn as {have}')
            for n in want:
                net_comps[n].add(c)
        for n, cs in net_comps.items():
            if len(cs) > 1:
                errs.append(f'net {n} is split into {len(cs)} unconnected pieces')
        if errs:
            raise SystemExit('drawing error:\n  ' + '\n  '.join(errs))

    # ----- output
    def emit(self, paper, title_notes):
        o = ['(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")',
             f'(uuid {q(self.root)}) (paper "{paper}")',
             '(title_block (title "Tesla Model S shunt board (RE)") (date "2026-11-02") (rev "auto")'
             ' (comment 1 "Generated by gen_schematic.py - edit the CSVs, not this file")'
             ' (comment 2 "Orange wire/label = inferred, red = unknown"))', '(lib_symbols']
        for lib_id in sorted({s['lib_id'] for s in self.syms}):
            lib, name = lib_id.split(':')
            o.append(kicad_symbol(lib, name) if lib != LIB else lib_symbol(name, prefix=LIB + ':'))
        for net in ('+5V', 'GND'):
            o.append(kicad_symbol('power', net))
        o.append(')')

        def colour_of(pt):
            return None

        for s in self.syms:
            p = self.byref[s['ref']]
            fa = s['rot'] % 180
            just = f"(justify {flip_just(s['just'], s['rot'])})" if s['just'] else ''
            val = p['value']
            o.append(f'(symbol (lib_id {q(s["lib_id"])}) (at {s["x"]} {s["y"]} {s["rot"]}) (unit {s["unit"]})'
                     ' (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)'
                     f' (uuid {q(U())})'
                     f' (property "Reference" {q(s["ref"])} (at {s["ref_at"][0]} {s["ref_at"][1]} {fa}) (effects (font (size 1.524 1.524) (bold yes)) {just}))'
                     f' (property "Value" {q(val)} (at {s["val_at"][0]} {s["val_at"][1]} {fa}) (effects (font (size 1.27 1.27)) {just}))'
                     f' (property "Footprint" "" (at {s["x"]} {s["y"]} 0) {fnt(hide=True)})'
                     f' (property "Datasheet" "" (at {s["x"]} {s["y"]} 0) {fnt(hide=True)})'
                     f' (property "Description" {q(p["description"])} (at {s["x"]} {s["y"]} 0) {fnt(hide=True)})'
                     f' (property "Marking" {q(p["marking"])} (at {s["x"]} {s["y"]} 0) {fnt(hide=True)})'
                     f' (property "BoardXY" {q(p["board_x"] + "," + p["board_y"])} (at {s["x"]} {s["y"]} 0) {fnt(hide=True)})')
            for num in s['pins']:
                o.append(f' (pin {q(num)} (uuid {q(U())}))')
            o.append(f' (instances (project {q(PROJ)} (path {q("/" + self.root)} (reference {q(s["ref"])}) (unit {s["unit"]})))))')
        # wire colour = evidence of the net it carries
        pt_status = {}
        for k, pt in self.pin_at.items():
            pt_status[pt] = self.net_of[k][1]
        for a, b in self.segs:
            o.append(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {q(U())}))')
        for pt in self.junctions:
            o.append(f'(junction (at {pt[0]} {pt[1]}) (diameter 0) (color 0 0 0 0) (uuid {q(U())}))')
        net_status = {}
        for k, (net, st, _) in self.net_of.items():
            net_status[net] = min(net_status.get(net, 'unknown'), st, key=lambda x: RANK[x]) if net in net_status else st
        for net, p, d in self.labels:
            ang, just = {'L': (180, 'right bottom'), 'R': (0, 'left bottom'), 'U': (90, 'left bottom'),
                         'D': (270, 'right bottom')}[d]
            st = 'unknown' if net.startswith('?') else worst_status(self.net_of, net)
            c = None if RANK[st] <= 2 else COL[st]
            o.append(f'(label {q(net)} (at {p[0]} {p[1]} {ang}) {fnt(color=c, justify=just)} (uuid {q(U())}))')
        for i, (net, p, d) in enumerate(self.powers, 1):
            rot = {('+5V', 'U'): 0, ('+5V', 'D'): 180, ('+5V', 'L'): 90, ('+5V', 'R'): 270,
                   ('GND', 'D'): 0, ('GND', 'U'): 180, ('GND', 'L'): 270, ('GND', 'R'): 90}[(net, d)]
            gx, gy = {'U': (0, -1), 'D': (0, 1), 'L': (-1, 0), 'R': (1, 0)}[d]
            vx, vy = p[0] + gx * (3.6 if gx else 0), p[1] + gy * (3.9 if gy else 0)
            just = '' if not gx else flip_just('(justify left)' if gx > 0 else '(justify right)', rot)
            hide = ' (hide yes)' if (gx and net == 'GND') else ''
            ref = f'#PWR{i:03d}'
            o.append(f'(symbol (lib_id "power:{net}") (at {p[0]} {p[1]} {rot}) (unit 1)'
                     ' (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)'
                     f' (uuid {q(U())})'
                     f' (property "Reference" {q(ref)} (at {p[0]} {p[1]} 0) {fnt(hide=True)})'
                     f' (property "Value" {q(net)} (at {vx:.2f} {vy:.2f} {rot % 180}) (effects (font (size 1.27 1.27)) {just}{hide}))'
                     f' (property "Footprint" "" (at {p[0]} {p[1]} 0) {fnt(hide=True)})'
                     f' (property "Datasheet" "" (at {p[0]} {p[1]} 0) {fnt(hide=True)})'
                     f' (pin "1" (uuid {q(U())}))'
                     f' (instances (project {q(PROJ)} (path {q("/" + self.root)} (reference {q(ref)}) (unit 1)))))')
        for t, p, size, bold in self.texts:
            o.append(f'(text {q(t)} (exclude_from_sim no) (at {p[0]} {p[1]} 0) {fnt(size, bold=bold, justify="left bottom")} (uuid {q(U())}))')
        for i, t in enumerate(title_notes):
            o.append(f'(text {q(t)} (exclude_from_sim no) (at 20.32 {NOTES_Y + i * 3.302:.2f} 0) {fnt(1.27, justify="left bottom")} (uuid {q(U())}))')
        o.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))')
        return '\n'.join(o)


def worst_status(net_of, net):
    sts = [st for (n, st, _) in net_of.values() if n == net]
    return max(sts, key=lambda s: RANK[s]) if sts else 'unknown'


# ---------------------------------------------------------------- the circuit, block by block
NOTES_Y = 378.46


def decap(sh, ref, x, y_top, top_net):
    """Decoupling / bulk cap drawn on its own: supply on top, GND below."""
    a, b = sh.two(ref, x, y_top + 3.81, 'v', top_net)
    sh.end(top_net, a, 'U')
    sh.end('GND', b, 'D')


def draw_sense_filter(sh, rshh_y, rshh_x):
    """Shunt -> R14 -> R15 -> IHM RSHH: two RC low-pass stages (C14, C13 to the RSHL/GND side)."""
    y = rshh_y
    sh.text('Current-sense input filter', 96.52, 82.55)
    # shunt bar, drawn vertically: SHUNT_HI on top, GND end at the bottom
    pins = sh.place('RS1', 106.68, y + 10.16, 90, ref_at=(102.87, y + 8.89), val_at=(102.87, y + 11.43), just='right')
    top, bot = (pins['2'], pins['1']) if pins['2'][1] < pins['1'][1] else (pins['1'], pins['2'])
    sh.end('GND', bot, 'D')
    r14a, r14b = sh.two('R14', 124.46, y, 'h', 'SHUNT_HI')
    node_hi = (114.3, y)
    sh.wire(top, (top[0], y), r14a)
    sh.wire(node_hi, (node_hi[0], y - 5.08))
    sh.label('SHUNT_HI', (node_hi[0], y - 5.08), 'U')
    c14a, c14b = sh.two('C14', 134.62, y + 3.81, 'v', 'IHM_RSH_MID')
    r15a, r15b = sh.two('R15', 147.32, y, 'h', 'IHM_RSH_MID')
    sh.wire(r14b, c14a, r15a)
    sh.end('GND', c14b, 'D')
    sh.label('IHM_RSH_MID', (r14b[0] + 1.27, y), 'R')
    c13a, c13b = sh.two('C13', 157.48, y + 3.81, 'v', 'IHM_RSHH')
    sh.wire(r15b, c13a, (rshh_x, y))
    sh.end('GND', c13b, 'D')
    sh.label('IHM_RSHH', (160.02, y), 'R')


def draw_ihm(sh):
    X, Y = 195.58, 110.49
    sh.text('Current-sense ASIC (IHM-A-1500)', 177.8, 82.55)
    pins = sh.place('U2', X, Y, 0, ref_at=(X - 16.51, Y - 13.97), val_at=(X - 16.51, Y - 11.43), just='right')
    # supply pins on top joined to the IHM_VDDD rail; EZPRG pulled up to the same rail through R17
    vdda, vddd, ezprg = pins['13'], pins['12'], pins['6']
    rail = 85.09
    a, b = sh.two('R17', ezprg[0], ezprg[1] - 6.35, 'v', 'IHM_VDDD')
    sh.wire(ezprg, b)
    sh.wire(vdda, (vdda[0], rail))
    sh.wire(vddd, (vddd[0], rail))
    sh.wire((vdda[0] - 5.08, rail), (vdda[0], rail), (vddd[0], rail), (a[0], rail), a)
    sh.label('IHM_VDDD', (vdda[0] - 5.08, rail), 'L')
    # ground pins and the REF / AGND caps underneath
    for n in ('5', '7'):
        sh.end('GND', pins[n], 'D')
    ref, agnd = pins['14'], pins['15']
    y_ag, y_rf = agnd[1] + 2.54, agnd[1] + 7.62
    ca, cb = sh.two('C19', 231.14, y_ag + 3.81, 'v', 'IHM_AGND')
    sh.wire(agnd, (agnd[0], y_ag), ca)
    sh.label('IHM_AGND', (agnd[0] + 2.54, y_ag), 'R')
    sh.end('GND', cb, 'D')
    xa, xb = sh.two('X1', 215.9, y_rf + 3.81, 'v', 'IHM_REF')
    sh.wire(ref, (ref[0], y_rf), xa)
    sh.label('IHM_REF', (ref[0] + 2.54, y_rf), 'R')
    sh.end('GND', xb, 'D')
    # RSHL and VBAT tie to GND (the shunt end the board is bonded to)
    rshl, vbat = pins['1'], pins['4']
    x_g = rshl[0] - 2.54
    sh.wire(rshl, (x_g, rshl[1]), (x_g, vbat[1]), vbat)
    sh.power('GND', (x_g - 2.54, rshl[1]), 'L')
    sh.wire((x_g, rshl[1]), (x_g - 2.54, rshl[1]))
    # decoupling for the IHM supply rail
    decap(sh, 'C17', 167.64, 124.46, 'IHM_VDDD')
    decap(sh, 'C18', 177.8, 124.46, 'IHM_VDDD')
    return pins


def draw_mcu(sh, ihm_pins):
    X, Y = 289.56, 121.92
    sh.text('MCU (STM8AF6266)', 271.78, 82.55)
    pins = sh.place('U1', X, Y, 0, ref_at=(X - 27.94, Y - 24.13), val_at=(X - 27.94, Y - 21.59 - 0.0), just='left')
    # direct links to the IHM: SDAT, CLK, SCLK, INTN, with the SDAT pull-up R18 to IHM_VDDD
    links = [('28', '10', 'IHM_SDAT'), ('25', '8', 'IHM_CLK'), ('27', '9', 'IHM_SCLK'), ('29', '11', 'IHM_INTN')]
    for mp, ip, net in links:
        a, b = ihm_pins[ip], pins[mp]
        assert a[1] == b[1], (net, a, b)
        sh.wire(a, b)
        sh.label(net, (a[0] + 2.54, a[1]), 'R')
    sd = ihm_pins['10']
    tap_x = 241.3
    r18a, r18b = sh.two('R18', tap_x, sd[1] - 8.89, 'v', 'IHM_VDDD')
    sh.wire((tap_x, sd[1]), r18b)
    sh.label('IHM_VDDD', r18a, 'U')
    # five GPIOs ganged together power the IHM
    group = [pins[n] for n in ('2', '3', '19', '31', '32')]
    xg = group[0][0] - 2.54
    for p_ in group:
        sh.wire(p_, (xg, p_[1]))
    sh.wire((xg, group[0][1]), (xg, group[-1][1]))
    sh.wire((xg, group[0][1]), (xg - 5.08, group[0][1]))
    sh.label('IHM_VDDD', (xg - 5.08, group[0][1]), 'L')
    # supplies on top, joined to one +5V
    t = [pins[n] for n in ('6', '7', '9')]
    yj = t[0][1] - 2.54
    for p_ in t:
        sh.wire(p_, (p_[0], yj))
    sh.wire((t[0][0], yj), (t[-1][0], yj))
    sh.wire((t[1][0], yj), (t[1][0], yj - 2.54))
    sh.power('+5V', (t[1][0], yj - 2.54), 'U')
    decap(sh, 'C6', 330.2, 85.09, '+5V')
    # grounds and the VCAP regulator cap at the bottom
    for n in ('4', '10'):
        sh.end('GND', pins[n], 'D')
    vcap = pins['5']
    yv = vcap[1] + 2.54
    ca, cb = sh.two('C15', 309.88, yv + 3.81, 'v', 'VCAP')
    sh.wire(vcap, (vcap[0], yv), ca)
    sh.label('VCAP', (vcap[0] + 2.54, yv), 'R')
    sh.end('GND', cb, 'D')
    return pins


def draw_connector(sh, mcu_pins):
    sh.text('Harness connector', 360.68, 82.55)
    # J1 row "PIN7" lines up with U1 PB2 so the six signals run straight across
    j_row0 = mcu_pins['14'][1] - 2 * PITCH
    X = 383.54
    hh = ic_symbol('CONN8')[2]
    Y = j_row0 + hh - PITCH
    jp = sh.place('J1', X, Y, 0, ref_at=(X, Y - hh - 1.27), val_at=(X, Y + hh + 1.27), just='')
    links = [('14', '7', 'OC_FLAG'), ('17', '3', 'SPI_NSS'), ('22', '4', 'SPI_SCK'), ('24', '5', 'SPI_MISO'),
             ('23', '6', 'SPI_MOSI'), ('21', '8', 'PIN8_PC4')]
    for mp, cp, net in links:
        a, b = mcu_pins[mp], jp[cp]
        assert a[1] == b[1], (net, a, b)
        sh.wire(a, b)
        sh.label(net, (a[0] + 2.54, a[1]), 'R')
    # OC_FLAG pull-up (R5) sits on the flag line
    fl = mcu_pins['14']
    tap = 350.52
    a, b = sh.two('R5', tap, fl[1] - 8.89, 'v', '+5V')
    sh.wire((tap, fl[1]), b)
    sh.end('+5V', a, 'U')
    # supply pins
    for n, net in (('1', '+5V'), ('2', 'GND')):
        p_ = jp[n]
        e = (p_[0] - 5.08, p_[1])
        sh.wire(p_, e)
        sh.end(net, e, 'L')
    decap(sh, 'C1', 398.78, 92.71, '+5V')
    return jp


def draw_programming(sh):
    x0, y0 = 429.26, 97.79
    sh.text('SWIM programming pads + reset', x0 - 5.08, 82.55)
    nets = {'P1': '+5V', 'P2': 'SWIM', 'P3': 'GND', 'P4': 'NRST'}
    for i, ref in enumerate(('P1', 'P2', 'P3', 'P4')):
        y = y0 + i * 5.08
        pins = sh.place(ref, x0 + 10.16, y, 0, ref_at=(x0 + 12.7, y), val_at=(x0 + 19.05, y), just='left')
        p_ = pins['1']
        e = (p_[0] - 5.08, p_[1])
        sh.wire(p_, e)
        sh.end(nets[ref], e, 'L')
    # NRST: 13.3k pull-up + cap to ground
    yn = y0 + 30.48
    node = (x0 + 10.16, yn)
    sh.wire((x0, yn), node)
    sh.label('NRST', (x0, yn), 'L')
    a, b = sh.two('R16', node[0], yn - 3.81, 'v', '+5V')
    sh.end('+5V', a, 'U')
    c, d = sh.two('C16', node[0], yn + 3.81, 'v', 'NRST')
    sh.end('GND', d, 'D')


def draw_comparators(sh):
    sh.text('Bidirectional overcurrent detector (LM2903)', 93.98, 190.5)
    cx = 162.56
    bus_x = 185.42
    outs = []
    # unit: (unit no, centre y, +IN resistor, +IN source net, -IN resistor, -IN source net,
    #        pull-ups on +IN, pull-downs on -IN, cap across inputs)
    units = [
        (1, 213.36, 'R8', 'SHUNT_HI', 'R10', 'GND', ['R7', 'R6'], ['R3', 'R4'], 'C8', 'CMP1_INP', 'CMP1_INN'),
        (2, 259.08, 'R11', 'GND', 'R9', 'SHUNT_HI', ['R13'], [], 'C10', 'CMP2_INP', 'CMP2_INN'),
    ]
    for unit, cy, r_p, src_p, r_n, src_n, ups, downs, cap, n_p, n_n in units:
        pins = sh.place('U3', cx, cy, 0, unit=unit, ref_at=(cx + 2.54, cy - 5.08), val_at=(cx + 2.54, cy + 5.08), just='left')
        inp, inn, out = pins['3' if unit == 1 else '5'], pins['2' if unit == 1 else '6'], pins['1' if unit == 1 else '7']
        y_p, y_n = inp[1] - 2.54, inn[1]                       # +IN rail sits 7.62 above the -IN rail
        x0 = 104.14
        a, b = sh.two(r_p, x0, y_p, 'h', src_p, fields='above2')
        sh.end(src_p, (a[0] - 5.08, y_p), 'L')
        sh.wire((a[0] - 5.08, y_p), a)
        a2, b2 = sh.two(r_n, x0, y_n, 'h', src_n, fields='below2')
        sh.end(src_n, (a2[0] - 5.08, y_n), 'L')
        sh.wire((a2[0] - 5.08, y_n), a2)
        turn = inp[0] - 2.54
        sh.wire(b, (turn, y_p), (turn, inp[1]), inp)
        sh.wire(b2, inn)
        sh.label(n_p, (b[0] + 1.27, y_p), 'R')
        sh.label(n_n, (b2[0] + 1.27, y_n), 'R')
        ca, cb = sh.two(cap, turn - 5.08, y_p + 3.81, 'v', n_p, fields='left')
        for k, r in enumerate(ups):
            x = 124.46 + k * 10.16
            ra, rb = sh.two(r, x, y_p - 5.08, 'v', '+5V')
            sh.wire((x, y_p), rb)
            sh.end('+5V', ra, 'U')
        for k, r in enumerate(downs):
            x = 124.46 + k * 10.16
            ra, rb = sh.two(r, x, y_n + 5.08, 'v', n_n)
            sh.wire((x, y_n), ra)
            sh.end('GND', rb, 'D')
        sh.wire(out, (bus_x, out[1]))
        outs.append(out)
        if unit == 2:
            # hysteresis: R12 from the flag back to +IN2
            y_fb = y_p - 12.7
            x_tap = 144.78
            fa, fb = sh.two('R12', 165.1, y_fb, 'h', 'CMP2_INP')
            sh.wire((x_tap, y_p), (x_tap, y_fb), fa)
            sh.wire(fb, (bus_x, y_fb))
    sh.wire((bus_x, outs[0][1]), (bus_x, outs[1][1]))
    sh.wire((bus_x, outs[0][1]), (bus_x + 7.62, outs[0][1]))
    sh.label('OC_FLAG', (bus_x + 7.62, outs[0][1]), 'R')
    sh.text('open-collector outputs, wired-OR', bus_x + 2.54, outs[1][1] + 5.08, 1.27, False)
    # supply unit + decoupling
    pins = sh.place('U3', 213.36, 236.22, 0, unit=3, ref_at=(215.9, 232.41), val_at=(215.9, 240.03), just='left')
    sh.end('+5V', pins['8'], 'U')
    sh.end('GND', pins['4'], 'D')
    decap(sh, 'C7', 236.22, 228.6, '+5V')
    decap(sh, 'C11', 246.38, 228.6, '+5V')


def draw_grid(sh, refs, x0, y0, title, cols=3, dx=45.72, dy=10.16):
    sh.text(title, x0, y0 - 7.62)
    for i, r in enumerate(refs):
        x, y = x0 + 15.24 + (i % cols) * dx, y0 + (i // cols) * dy
        kind = sh.byref[r]['kind']
        if kind == 'TP':
            sh.place(r, x, y, 0, ref_at=(x + 2.54, y), val_at=(x + 9.53, y), just='left')
        elif kind in STD_SYMBOLS:
            sh.place(r, x, y, 90, fields='above')
        else:
            sh.place(r, x, y, 0, fields='above')


def build(parts, net_of):
    sh = Sheet(U(), parts, net_of)
    ihm = draw_ihm(sh)
    draw_sense_filter(sh, ihm['2'][1], ihm['2'][0])
    mcu = draw_mcu(sh, ihm)
    draw_connector(sh, mcu)
    draw_programming(sh)
    draw_comparators(sh)
    drawn = {s['ref'] for s in sh.syms}
    conn_parts = [p['ref'] for p in parts if p['ref'] not in drawn and p['kind'] != 'TP' and p['kind'] not in SYMBOLS]
    tps = [p['ref'] for p in parts if p['ref'] not in drawn and p['kind'] == 'TP']
    draw_grid(sh, conn_parts, 281.94, 205.74, 'Connector-side parts (nets not measured yet)')
    draw_grid(sh, tps, 434.34, 205.74, 'Test pads', cols=3, dx=38.1, dy=7.62)
    missing = [p['ref'] for p in parts if p['ref'] not in {s['ref'] for s in sh.syms}]
    assert not missing, f'not drawn: {missing}'
    sh.finish()
    return sh.emit('A2', NOTES)



def write_lib(parts):
    kinds = sorted({p['kind'] for p in parts} - set(STD_SYMBOLS))
    s = ['(kicad_symbol_lib (version 20241209) (generator "gen_schematic.py") (generator_version "9.0")']
    for k in kinds:
        s.append(lib_symbol(k))
    s.append(')')
    open(os.path.join(HERE, f'{LIB}.kicad_sym'), 'w').write('\n'.join(s))
    open(os.path.join(HERE, 'sym-lib-table'), 'w').write(
        f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") (options "") (descr "Shunt board RE symbols")))\n')
    pro = os.path.join(HERE, f'{PROJ}.kicad_pro')
    if not os.path.exists(pro):
        open(pro, 'w').write('{"meta": {"filename": "%s.kicad_pro", "version": 1}}\n' % PROJ)


# ---------------------------------------------------------------- self-check
def check_with_kicad(net_of):
    sch = os.path.join(HERE, f'{PROJ}.kicad_sch')
    out = os.path.join(HERE, 'build', f'{PROJ}.net')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', out, sch],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        return False
    txt = open(out).read()
    got = {}
    for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "((?:[^"\\]|\\.)*)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)', txt, re.S):
        name = m.group(1).lstrip('/')
        for n in re.finditer(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', m.group(2)):
            got[(n.group(1), n.group(2))] = name
    bad = []
    by_csv, by_kicad = defaultdict(set), defaultdict(set)
    for k, v in net_of.items():
        by_csv[v[0]].add(k)
        by_kicad[got.get(k)].add(k)
    for net, ks in by_csv.items():
        kn = {got.get(k) for k in ks}
        if len(kn) != 1:
            bad.append((net, 'split across', kn))
            continue
        kname = kn.pop()
        if by_kicad[kname] != ks:
            bad.append((net, 'shares KiCad net with', sorted(by_kicad[kname] - ks)[:6]))
        auto = kname is None or kname.startswith(('Net-(', 'unconnected-'))
        if not auto and kname != net and not net.startswith('?'):
            bad.append((net, 'named', kname))
    if bad:
        print('NETLIST MISMATCH:')
        for b_ in bad[:30]:
            print('  ', b_)
        return False
    print(f'self-check OK: KiCad connectivity matches connections.csv for all {len(net_of)} pins')
    return True


def main():
    parts, conns, meas = load()
    net_of, errs = resolve(parts, conns)
    # measurement constraints: "open" results must not be contradicted
    for m in meas:
        if m['result'] != 'open':
            continue
        ka, kb = (tuple(m[x].split('.')) for x in ('a', 'b'))
        na = net_of.get(ka, (None,))[0] if ka in net_of else (m['a'] if m['a'] in ('GND', '+5V') else None)
        nb = net_of.get(kb, (None,))[0] if kb in net_of else (m['b'] if m['b'] in ('GND', '+5V') else None)
        if na and na == nb:
            errs.append(f'measurement {m["id"]}: {m["a"]} and {m["b"]} measured open but share net {na}')
    if errs:
        print('\n'.join(errs))
        sys.exit(1)
    write_lib(parts)
    open(os.path.join(HERE, f'{PROJ}.kicad_sch'), 'w').write(build(parts, net_of))
    st = defaultdict(int)
    for v in net_of.values():
        st[v[1]] += 1
    print('pins by status:', dict(st))
    ok = check_with_kicad(net_of)
    if ok:
        subprocess.run(['kicad-cli', 'sch', 'export', 'pdf', '-o', os.path.join(HERE, 'build', f'{PROJ}.pdf'),
                        os.path.join(HERE, f'{PROJ}.kicad_sch')], capture_output=True)
        r = subprocess.run(['kicad-cli', 'sch', 'erc', '-o', os.path.join(HERE, 'build', 'erc.rpt'),
                            os.path.join(HERE, f'{PROJ}.kicad_sch')], capture_output=True, text=True)
        dang = open(os.path.join(HERE, 'build', 'erc.rpt')).read().count('[label_dangling]')
        print(f'wrote build/{PROJ}.pdf | unresolved single-ended nets (ERC label_dangling): {dang}')
    sys.exit(0 if ok else 2)


if __name__ == '__main__':
    main()
