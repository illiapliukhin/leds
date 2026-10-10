# Electrical / BOM issues (report only — PCB not modified here)

Findings from schematic ↔ PCB cross-check and architecture docs (`MONO_SPLIT_ARCHITECTURE.md`, `MONO_ELECTRONICS_BACKLOG.md`, `DATASHEET_BOM_FREEZE.md`).

## Blocking / high priority

1. **USB-C CC1/CC2 missing 5.1 kΩ pulldowns to GND** on `J_USB` (sink/UFP). C-to-C VBUS may not turn on. Documented in backlog; **not present on PCB or schematic manifest**.
2. **`MIC1`, `U_AUDIO`, `U_GAUGE` have no pad nets on the committed PCB** — footprints placed but unrouted (open pads). Audio/gauge path is not electrically closed.
3. **`TH_PCB` (NTC placeholder)** has no nets on PCB; pack NTC uses `TS_MR` on `J_BAT` only (per architecture).

## Medium priority

4. **`mono_electronics` DRC**: copper 0/0 but **26 unconnected groups** (AON/GND islands + signals) per `hardware/LAST_CHANGES.md` — fab for electronics is **NOT_READY**.
5. **LED rail divider** uses **681 kΩ / 91 kΩ → ~4.24 V** (`LED_4V1`), not RGB 655/91 kΩ — verify farthest white pixel drop vs MBI5124 `VDS` (EVT).
6. **MBI5124 CLK margin**: 25 MHz max vs 20 MHz baseline — SI/timing EVT required before 24 MHz.
7. **Row high-side `AO3403`**: Vgs −2.5 V worst-case, Qg ~2.8 nC — row dead-time and drop are EVT.
8. **ESP32 strapping**: `GPIO0` has `R_BOOT0` + `SW1`; confirm `GPIO3/45/46` are not driven as outputs (FN8 map — pad 32 `SPICS0` must stay NC).

## LCSC / BOM gaps

9. Several passives in `lcsc_bom_map.json` are populated; **0402/0805 generics** and **Hirose FFC** need LCSC line items before JLC order.
10. **`DATASHEET_BOM_FREEZE.md`**: USB-C mechanical choice still OPEN — do not freeze USB placement for production.
