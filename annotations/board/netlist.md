# Shunt board netlist (extracted from photos)

> **Superseded for netlist data by [`../../schematic/`](../../schematic/README.md)**
> (`connections.csv` is now the source of truth; `measurements.csv` holds meter results).
> This file is the original photo-based reasoning. Later measurements overturned some of it:
> ETS/ETR are **not** connected to the centre cluster or to R14/R15 (no temperature sensor), the
> centre cluster is GND/bar, and OUT1+OUT2 are wired together to connector PIN7.

Sources: `Traces-and-pins.jpeg` (top side, ~59 px/mm), the microscope shots in `photos/`
(`stm8-1/3`, `IHM-A-1500-2`, `2903AVQ-1/3`, `2093AVQ-2`), and the three datasheets in `docs/`.
Reference designators are mine. See `netlist_overlay.jpg` for where each one sits on the board.

**Evidence tags**
- **[seen]**: copper visible end to end in at least one photo
- **[ds]**: forced by the datasheet (power pins, mandatory caps), near certain
- **[inf]**: inferred from placement, part values, or circuit logic; not traced
- **[?]**: goes to an inner or bottom layer, so it can't be resolved from top-side photos

Only the top side was photographed. The connector pins solder on the far side, and most
signal routing visibly drops into vias. Anything that runs connector↔MCU or MCU↔IHM is
therefore at best [inf] until someone checks it with a meter (see the checklist at the end).

---

## Corrections to the current annotation

1. **UART_RX / UART_TX are swapped.** Pin 1 is bottom-left (confirmed by the package dot in
   `stm8-3`), so the left side reads pins 25→32 from top to bottom. The 6th pin from the top is
   **pin 30 = PD5 / LINUART_TX** and the 7th is **pin 31 = PD6 / LINUART_RX**. The via right
   next to the 7th pin is therefore **RX (PD6)**.
2. **The 2903 is the LM2903B-Q1 dual *comparator*, not a differential amplifier.**
   Its outputs are open-collector, so OUT1/OUT2 need pull-ups somewhere (probably at the
   receiving end).
3. **Resistor values from the markings** (in-circuit meter readings are skewed by parallel paths):

   | Marking (as photographed) | Reads | Value | Annotation had |
   |---|---|---|---|
   | `ZZEE` (×2, R6/R13) | `3322` upside down | **33.2 kΩ** | 7.5k |
   | `100Ч` / `h00I` (×2, R7/R12) | `1004` | **1.00 MΩ** | 11.2k |
   | `8200` / `0028` (×3, R10/R14/R15) | `8200` | **820 Ω** | 800 Ω |
   | `2200` / `0022` (×3, R8/R9/R11) | `2200` | **220 Ω** | 220 Ω ✓ |
   | `2701` (R5) | `2701` | **2.70 kΩ** | n/a |
   | `01E` (×2, R1/R2) | EIA-96 `01E` | **1.00 MΩ** | n/a |
   | `E2A` / `E23` (R3/R4) | `823`, one upside down | **82 kΩ** | n/a |
   | `18C` (×2, R17/R18) | EIA-96 | **15.0 kΩ** | n/a |
   | `13C` (R16) | EIA-96 | **13.3 kΩ** | n/a |

   A 1 MΩ / 33.2 kΩ divider from 5 V gives **≈160 mV**. That is the comparator trip threshold
   (see U3), so these values fit the circuit.

---

## U1: STM8AF6266TC (LQFP32, 0.8 mm pitch)

Orientation: pin 1 at bottom-left. Bottom row = 1→8 (left→right), right side = 9→16
(bottom→top), top row = 17→24 (right→left), left side = 25→32 (top→bottom).

| Pin | Name | Connects to | Tag |
|---|---|---|---|
| 1 | NRST | Via just left of the pin. R16 (13.3 kΩ) and C16 next to it look like the reset network (pull-up + filter cap) | [inf] |
| 2 | PA1/OSCIN | No crystal on the top side; likely unused (HSI clock) | [?] |
| 3 | PA2/OSCOUT | as pin 2 | [?] |
| 4 | VSS | GND | [ds] |
| 5 | VCAP | Needs a 470 nF–3.3 µF ceramic to VSS. Test pad directly below the pin; cap not identified on top (C15 1206 is the candidate) | [ds]/[?] |
| 6 | VDD | +5 V | [ds] |
| 7 | VDDIO | +5 V | [ds] |
| 8 | PF4/AIN12 | not resolved | [?] |
| 9 | VDDA | +5 V via the VDD via to the right; **C6** (0603) is the VDDA–VSSA decoupling cap | [seen]/[ds] |
| 10 | VSSA | GND, C6 | [ds] |
| 11 | PB5/AIN5 (I2C_SDA alt) | not resolved; annotation calls it SDA, but no I²C device is on the board | [?] |
| 12 | PB4/AIN4 (I2C_SCL alt) | as pin 11 | [?] |
| 13/14 | PB3/AIN3, PB2/AIN2 | One of these (most likely **14, PB2/AIN2**) runs right to **R5 (2.70 kΩ)**, whose other pad goes to a via. Probably a series resistor on an ADC input | [seen] (pin uncertain by ±1) |
| 15 | PB1/AIN1 | not resolved | [?] |
| 16 | PB0/AIN0 | not resolved | [?] |
| 17 | PE5/SPI_NSS | Connector NSS (through vias) | [inf] |
| 18–21 | PC1–PC4 (TIM1_CH1–4) | Two square test pads above the top row each tie to one of these pins; traces continue up toward the connector | [seen] partial |
| 22 | PC5/SPI_SCK | Connector SCK | [inf] |
| 23 | PC6/SPI_MOSI | Connector MOSI; a via above pins 23/24 takes one of them down | [inf] |
| 24 | PC7/SPI_MISO | Connector MISO | [inf] |
| 25 | PD0 / TIM3_CH2 / **CLK_CCO** (AFR2) | → test pad → via (left) → **IHM CLK (U2 pin 8)**. PD0's CLK_CCO alternate function outputs the CPU clock, which is the obvious way to feed the IHM's 8.192 MHz master clock | [seen] to via; via→U2 [inf] |
| 26 | PD1 / **SWIM** | Long trace to the left-edge pad **P2**, which makes P1–P4 the SWIM/ICT programming pads (P1 = VDD) | [seen] |
| 27 | PD2 / TIM3_CH1 | → via → square test pad just below → **IHM SCLK (U2 pin 9)** | [seen] to via; via→U2 [inf] |
| 28 | PD3 / TIM2_CH2 / ADC_ETR | → square test pad → **IHM SDAT (U2 pin 10)** | [seen] to TP; TP→U2 [inf] |
| 29 | PD4 / TIM2_CH1 / BEEP | Diagonal trace → test pad (left-lower). Candidate for **IHM INTN** (interrupt) | [seen] to TP; →INTN [inf] |
| 30 | PD5 / **LINUART_TX** | not resolved | [?] |
| 31 | PD6 / **LINUART_RX** | Via immediately left of the pin | [seen] |
| 32 | PD7 / TLI | not resolved (TLI is also a good INTN candidate) | [?] |

---

## U2: IHM-A-1500 (SOIC16)

Orientation: pin 1 top-right. Top row = 1→8 (right→left), bottom row = 9→16 (left→right).

| Pin | Name | Connects to | Tag |
|---|---|---|---|
| 1 | RSHL | Shunt low-side Kelvin sense (via cluster / R14·R15 filter region). Also the analog common | [inf] |
| 2 | RSHH | Shunt high-side Kelvin sense | [inf] |
| 3 | ETS | Trace runs up, then right along y≈2055 into the **center via cluster** | [seen] |
| 4 | VBAT | Trace runs up, then right along y≈2000 into the **center via cluster** | [seen] |
| 5 | VSS | GND | [ds] |
| 6 | EZPRG | Datasheet: open or tied to VDDD | [ds] |
| 7 | VSSD | GND | [ds] |
| 8 | CLK | Via above-left ("IHM CLK") → U1 PD0 | [seen] to via |
| 9 | SCLK | U1 PD2 (through vias) | [inf] |
| 10 | SDAT | U1 PD3 (through vias); R17/R18 (15 kΩ) are pull-up candidates | [inf] |
| 11 | INTN | U1 PD4 or PD7 | [inf] |
| 12 | VDDD | Trace up and left to the "IHM VDDD" via; **C17/C18** sit next to it (decoupling) | [seen] |
| 13 | VDDA | +5 V (VDDD region) | [ds] |
| 14 | REF | → test pad → **X1** below it, which is most likely the 30 nF REF cap to VSS (datasheet) | [seen] to TP |
| 15 | AGND | → test pad → **C19** below it (50–100 nF to VSS per datasheet; no direct tie to VSS allowed) | [seen] to TP |
| 16 | ETR | Toward R14/C13/C14/R15 (the 820 Ω + 2-cap network at the pin-1/16 end) | [inf] |

**R14 / C13 / C14 / R15** (820 Ω, 2× 0603 C, 820 Ω) sit right next to U2's pin-1/16 end, between it
and the via cluster. That is the classic differential RC input filter. My best guess is that it
filters RSHH/RSHL (or ETS/VBAT) on their way to the shunt, but I couldn't follow the copper.

**Center via cluster** (8 vias in two zig-zag columns, directly over the middle of the copper
bar, i.e. over the resistive element): this is where the board connects down to the shunt.
VBAT and ETS both route here, so the cluster is **not all VSS**. Most likely one column is the
SHUNT_A-side Kelvin connection and the other is SHUNT_B. VBAT/ETS sensing the shunt gives the
IHM a second, independent measurement channel. Check the cluster with a meter (checklist below).

---

## U3: LM2903B-Q1 (SOIC8): bidirectional hardware overcurrent detector

Orientation: pin 1 top-right (board view). Top row = 1→4 (right→left), bottom row = 5→8 (left→right).

| Pin | Name | Connects to | Tag |
|---|---|---|---|
| 1 | OUT1 | Joins the **edge bus** (≈5–6 parallel traces along the right board edge) | [seen] onto bus |
| 2 | 1IN− | **C8** (0805) across 1IN+/1IN−; threshold node (see below) | [seen] C8 |
| 3 | 1IN+ | **C8**; SH_A through **R8 (220 Ω)** from the SHUNT_A via | [seen] R8/via adjacency, [inf] |
| 4 | GND | VSS | [ds] |
| 5 | 2IN+ | **C10** (0805) across 2IN+/2IN−; SH_B through 220 Ω (R11 or R9) | [seen] C10, [inf] |
| 6 | 2IN− | **C10**; threshold node | [seen] C10 |
| 7 | OUT2 | Joins the edge bus | [seen] onto bus |
| 8 | VCC | Joins the edge bus (+5 V) | [seen] onto bus |

**Reconstructed circuit (from the values; [inf]):**

```
SHUNT_A ──R8 220Ω──┬── 1IN+          VDD ──R7 1MΩ──┬── 1IN−
                   C8 (across)        SHUNT_B ─R6 33.2k─┘
SHUNT_B ──R11 220Ω─┬── 2IN+          VDD ──R12 1MΩ─┬── 2IN−
                   C10 (across)       SHUNT_A ─R13 33.2k─┘
```

Each "−" input sits at the opposite shunt node plus a 5 V × 33.2k / 1033.2k ≈ **+160 mV** offset.
OUT1 releases when V(A)−V(B) > 160 mV, and OUT2 when V(B)−V(A) > 160 mV: a ±160 mV window
across the shunt in both current directions. The divider pairs sit directly beside each
"−" pin (R6/R7 above pin 2, R12/R13 below pin 6), which supports this reading. The cross-feeds
to the far shunt node would use the edge bus. R9 (220 Ω), R10 (820 Ω) and their test pads are
between the SHUNT_A and SHUNT_B vias. Their exact role (second 220 Ω path, or a bias/filter
for the comparator) is unresolved.

**Where OUT1/OUT2 go:** the edge bus runs up to the connector end. Connector **PIN 7 / PIN 8**
(unlabelled so far) are the prime suspects for the two overcurrent flags, with R1–R4
(1 MΩ / 82 kΩ) and C3–C5 near the top-right as their pull/filter parts. That would make the
shunt report a hardware overcurrent to the BMS without involving the MCU. [inf]

---

## Connector-side parts (top strip)

| Ref | Part | Probable role | Tag |
|---|---|---|---|
| C1 | 1206 ceramic | VDD input bulk/filter cap (next to VDD pin) | [inf] |
| R1, R2 | 1.00 MΩ | Pull-downs/bleeds on connector lines | [inf] |
| D1, D2 | Small black 2-terminal with box symbol | ESD/TVS diodes on connector lines | [inf] |
| C2, C3, C4, C5 | 0603 | Line filter / decoupling caps | [inf] |
| R3, R4 | 82 kΩ | Pull-ups / dividers on PIN 7/8 lines | [inf] |

---

## Verification checklist (continuity, board unpowered)

These checks would turn every [inf] above into a fact. They are ordered by how much they settle.

1. Connector PIN 7 and PIN 8 → U3 pin 1 / pin 7 (OUT1/OUT2), and → any U1 pin.
2. U1 pin 25 (PD0) ↔ U2 pin 8 (CLK); pin 27 (PD2) ↔ U2 pin 9; pin 28 (PD3) ↔ U2 pin 10; pin 29 (PD4) or 32 (PD7) ↔ U2 pin 11.
3. Each via in the center cluster → SHUNT_A copper, SHUNT_B copper, U2 pins 1/2/3/4.
4. U3 pin 2 ↔ R6/R7 junction; U3 pin 6 ↔ R12/R13 junction; free ends of R6/R13 → which shunt side.
5. U1 pins 17, 22, 23, 24 → connector NSS/SCK/MOSI/MISO (and whether they pass through R1/R2/D1/D2).
6. P1–P4 left-edge pads: P1 = VDD, P2 = SWIM (confirmed). Check P3/P4 against NRST and VSS.
7. U1 pin 30 (TX) and 31 (RX) → anything (a test pad or connector pin would mean a debug UART).
