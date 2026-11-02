# Shunt board schematic (reverse-engineered)

Open `shunt.kicad_pro` in KiCad 9, or look at `build/shunt.pdf`.

**Don't edit the schematic by hand.** It's generated from CSVs plus the hand-written layout in `gen_schematic.py` (one `draw_*` function per circuit block). Edit those and regenerate:

```
python3 gen_schematic.py   # schematic + PDF, then checks itself against KiCad
python3 make_overlay.py    # annotations/board/netlist_overlay.jpg (pins, parts, pads, vias)
```

| File | What it holds |
|---|---|
| `parts.csv` | Every part: ref, value, marking, position on the board photo, functional group |
| `connections.csv` | One row per pin: `net`, `status`, `note`. **This is the netlist.** |
| `measurements.csv` | Meter results. An `open` result is enforced, so the generator refuses a netlist that contradicts it |
| `vias.csv` | Named probe points (V1–V25, centre cluster VC1–VC8) |
| `probe_log.html` | Entry page for meter readings (published at https://claude.ai/artifact/N3Y8tmFTnJZgiEhZ6fWMMt) |
| `probe_round2.md` | Round 2 test list (done; kept for reference) |

## Status values

| status | meaning | label colour |
|---|---|---|
| `measured` | confirmed with the meter | green |
| `seen` | copper visible in the photos | green |
| `datasheet` | forced by the datasheet (power pins, etc.) | green |
| `inferred` | from placement, values or circuit logic | orange |
| `unknown` | leave `net` empty; it becomes a unique `?REF.PIN` label | red |

Pin 1 of a passive is its top pad (vertical part) or left pad (horizontal part) as seen in
`annotations/board/Traces-and-pins.jpeg`.

## Workflow with the meter

1. Enter readings on the probe log page. Claude reads them from there.
2. Record each result:
   - **Connected:** set that pin's `net` to the net it joined, with status `measured`.
   - **Through a resistor:** if a point reads the value of a resistor, it connects via that part,
     so note which pad and set the nets on both pads.
   - **Not connected:** add a row to `measurements.csv` with result `open`.
3. Rerun `gen_schematic.py`. It prints how many single-ended (unresolved) nets remain. This is
   the ERC `label_dangling` count, and the goal is 0.

The self-check exports KiCad's own netlist and compares it pin by pin against
`connections.csv`, so the drawing and the data cannot drift apart.
