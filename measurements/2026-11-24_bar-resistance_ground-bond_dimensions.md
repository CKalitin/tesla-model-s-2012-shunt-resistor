# 2026-11-24: bar resistance, ground-bond end, dimensions

> ⚠️ **PRELIMINARY / UNCONFIRMED.** The meter readings sit at the DMM's 0.1 mV resolution limit, and the dimensions are first hand measurements. Re-measure before relying on any of this.

Used in the Tower A battery pack: [claude-battery-pack/docs/tesla-shunt.md](https://github.com/CKalitin/claude-battery-pack/blob/master/docs/tesla-shunt.md).

## Dimensions

| Feature | Value |
|---|---|
| Bar | 1/8" (3.175 mm) copper, 35 × 83.5 mm |
| Bolts | On the long centre line, 15 mm from each end (53.5 mm apart). Thread unknown |
| PCB | 2 mm thick, 25 mm wide, centred along the bar, overhanging the long edge by 8 mm (43 × 25 mm footprint). Components reach 5 mm above the copper |
| Connector | 10-pin Molex Mini-Fit (part TBD), key slot between pins 1 and 2. Top is 5 mm above the PCB (7 mm above the copper). Wires exit straight up |

## Bar resistance and ground-bond end

**Setup:**
- Bench supply in constant current, 5 A, bolt to bolt.
- DMM on the 200 mV range (0.1 mV resolution).
- COM on J1 pin 2 (GND) at the connector.
- Module powered from the NUCLEO.

| Measurement | Current on | Current off | Reversed |
|---|---|---|---|
| Bolt to bolt | 0.1 mV | — | — |
| J1 GND → bolt "A" (on supply − in the first run) | 0.0 mV | 0.0 mV | 0.0 mV |
| J1 GND → bolt "B" | +0.1 mV | 0.0 mV | −0.0 mV |

**Pitfall:** measuring against the NUCLEO GND (through a jumper) read about 3.5 mV on *both* bolts. That's an offset: module supply current × the jumper/contact resistance. Measure at the J1 pin and difference the current-on and current-off readings.

**Results:**
- **R_bar ≈ 20 µΩ** (0.1 mV / 5 A; one count, so 10–30 µΩ).
- **Bonded end: probably bolt "A"**, not conclusive, because bolt "B"'s sign flip on reversal is below one count. Mark bolt "A" physically.

## To do

- [ ] 4-wire R with a µV-resolution meter, or 20–50 A of test current; temperature coefficient.
- [ ] Repeat the bond test at real resolution.
- [ ] Bolt thread; connector part number; J1 pins 8–10.
