# Probe round 2

Every test is **two exact points** and gives **one number** (two if the reading isn't ~0, see rule 3).
Pad positions ("left/right/top/bottom") are as in `annotations/board/netlist_overlay.jpg`
(connector at the top). IC pin numbers are labelled on the overlay.
"Connector X" means that harness wire/pin by your label (VDD, VSS, NSS, SCK, MISO, MOSI, PIN7, PIN8).
"Bolt" means either shunt bolt (they read the same).

## Rules

1. Board unpowered, harness unplugged, ohms range.
2. **Short the probes together first and note the reading.** That number (your ~1 Ω) is the probe
   and lead resistance, not a real resistance. "Connected" = within ~1 Ω of it.
3. If a reading is **not** ~0, **swap the red and black probes and write both numbers**. If the two
   readings match, the path is through a resistor. If they differ, it runs through a chip's internals
   and can be ignored.
4. MΩ readings, or readings that keep climbing, mean "not connected" (a capacitor charging or chip
   leakage). Just write "open". That's what ETS did.
5. Report as `A1: 0`, `A2: 1.02M / 1.02M`, `B3: open`.

## A. Comparator: confirm the threshold dividers (replaces the vague "R6/R7 junction" test)

| ID | Probe 1 | Probe 2 | Expect if my theory is right |
|---|---|---|---|
| A1 | U3 pin 2 | R6 **right** pad | 0 |
| A2 | U3 pin 2 | R7 **left** pad | 0 |
| A3 | U3 pin 6 | R12 **left** pad | 0 |
| A4 | U3 pin 6 | R13 **right** pad | 0 |
| A5 | U3 pin 3 | R8 **top** pad | 0 |
| A6 | U3 pin 5 | R11 **bottom** pad | 0 |
| A7 | R7 **right** pad | Connector VDD | 0 |
| A8 | R12 **right** pad | Connector VDD | 0 |
| A9 | R6 **left** pad | Bolt | 0 |
| A10 | R13 **left** pad | Bolt | 0 |
| A11 | U3 pin 8 | Connector VDD | 0 |
| A12 | U3 pin 4 | Bolt | 0 |

If any of A1–A4 is not ~0, keep probe 1 on that U3 pin and touch every pad of R6, R7, R12, R13, C8
and C10 (12 pads). Report which pad is ~0, or "none".

## B. MCU ↔ IHM link

| ID | Probe 1 | Probe 2 | Expect |
|---|---|---|---|
| B1 | U1 pin 27 | U2 pin 9 (SCLK) | 0 |
| B2 | U1 pin 28 | U2 pin 10 (SDAT) | 0 |
| B3 | U1 pin 29 | U2 pin 11 (INTN) | 0, or open if it's B4 |
| B4 | U1 pin 32 | U2 pin 11 (INTN) | only needed if B3 is open |
| B5 | R17 top pad | U2 pin 10 | 0 if R17 pulls up SDAT |
| B6 | R18 top pad | U2 pin 11 | 0 if R18 pulls up INTN |
| B7 | R17 bottom pad | Connector VDD | 0 |
| B8 | R18 bottom pad | Connector VDD | 0 |

## C. Connector ↔ MCU

| ID | Probe 1 | Probe 2 | Expect |
|---|---|---|---|
| C1 | Connector NSS | U1 pin 17 | 0 |
| C2 | Connector SCK | U1 pin 22 | 0 |
| C3 | Connector MISO | U1 pin 24 | 0 |
| C4 | Connector MOSI | U1 pin 23 | 0 |
| C5 | Connector PIN8 | U1 pin 30 | ? |
| C6 | Connector PIN8 | U1 pin 31 | ? |
| C7 | Connector PIN8 | U1 pin 1 | ? |
| C8 | Connector PIN8 | U1 pin 26 | ? |
| C9 | Connector PIN7 | R3 left pad, R3 right pad, R4 left pad, R4 right pad | which one is 0 (finds the OC_FLAG pull-up) |

If C1–C4 read a resistor value (not 0, not open), the line has a series part. Then also probe that
connector pin to both pads of R1, R2, D1 and D2.

## D. IHM power and support parts

| ID | Probe 1 | Probe 2 | Expect |
|---|---|---|---|
| D1 | U2 pin 12 (VDDD) | Connector VDD | 0 (or a small resistor value = RC filter) |
| D2 | U2 pin 13 (VDDA) | Connector VDD | same as D1 |
| D3 | U2 pin 6 (EZPRG) | U2 pin 12 | 0 or open |
| D4 | U2 pin 6 (EZPRG) | Bolt | 0 or open |
| D5 | U2 pin 14 (REF) | X1 top pad | 0 |
| D6 | X1 bottom pad | Bolt | 0 |
| D7 | U2 pin 15 (AGND) | C19 top pad | 0 |
| D8 | C19 bottom pad | Bolt | 0 |
| D9 | C17 top pad | U2 pin 12 | 0 |
| D10 | C18 top pad | U2 pin 13 | 0 |

## E. MCU support

| ID | Probe 1 | Probe 2 | Expect |
|---|---|---|---|
| E1 | U1 pin 5 (VCAP) | C15 left pad | one of E1/E2 is 0 |
| E2 | U1 pin 5 (VCAP) | C15 right pad | |
| E3 | U1 pin 1 (NRST) | R16 top pad | one of E3/E4 is 0 |
| E4 | U1 pin 1 (NRST) | R16 bottom pad | |
| E5 | U1 pin 1 (NRST) | C16 top pad | one of E5/E6 is 0 |
| E6 | U1 pin 1 (NRST) | C16 bottom pad | |
| E7 | Left-edge pad P3 | U1 pin 1 | 0 if P1–P4 are the SWIM header |
| E8 | Left-edge pad P4 | Bolt | 0 |

## Optional: which end of the bar is which

Only matters for the sign of the current. It needs a bench supply that can push ≥5 A bolt to bolt.
Measure **mV** between R14 left pad and U2 pin 1. A non-zero reading confirms R14 sits on the
opposite end of the shunt to RSHL. Skip this unless you're curious.
