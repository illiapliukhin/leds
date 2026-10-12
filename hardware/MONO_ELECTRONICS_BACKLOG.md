# Mono electronics — backlog

Items below ship only through the **same gate** as PR #4 mono routing:

- Reproduce: `hardware/tools/generate_mono_split_boards.py` (one command).
- **Copper:** 0 shorts / 0 crossings (`copper_gate_counts` / `drc_gate_routes`).
- **Monotonic DRC:** unconnected and clearance must not regress vs the pre-step baseline (`monotonic_gate_allows` in `mcu_grid_drc.py`); post-grid sub-steps use per-step backup restore like `mono_split_post_grid_finish.py`.
- **PCB commit:** only when the pipeline end state meets the active unconnected target (currently **&lt;24** at 0/0/0) unless explicitly relaxed.

---

## 1. Full-board GND pour on In2 and B

**Problem:** After grid/refill, solid **GND zones** on **In2** and **B** only cover roughly **(1, 1)–(151, 137) mm** (see `ensure_gnd_copper_zones()` in `mcu_grid_route.py`: `margin_mm = 1.0`, `width_mm = 152`, `height_mm = 138`). The **right side** of the **190 × 148 mm** outline—**J_ROW / J_COL** FFC plugs and row/column **fan-in**—has **no GND copper pour**, so F-only GND pads and long signal returns depend on sparse tracks.

**Work:**

- Extend **In2** and **B** GND zone outlines to the **full board outline** minus **edge clearance** (match `apply_design_rules` / `min_copper_edge_clearance`, not the ad-hoc 152×138 box).
- **Stitch** the extended pour to existing GND (F escapes, matrix fan-in vias, USB shell, MCU GND spines) using the same gated flow as GND dogbones: one stitch at a time, refill, monotonic gate; prefer `GND_STITCH_FIXED_FALLBACK` / `MONO_FANOUT_GND_FIXED` only when search paths short/cross.
- Verify with DRC + zone refill that **J_ROW/J_COL** region shows filled GND on In2/B and that **unconnected GND** count drops without copper regression.

**Touchpoints:** `ensure_gnd_copper_zones()`, possibly `generate_electronics_board()` if zones belong in static generate; post-grid **`gnd`** phase / `stitch_gnd_pads_with_drc_gate`.

---

## 2. USB-C CC1 / CC2 — 5.1 kΩ to GND (sink / UFP)

**Problem:** **J_USB** (`USB4105` / HRO Type-C) has **no CC pulldowns**. Without **Rd = 5.1 kΩ** on **CC1** and **CC2** to **GND** on the **sink (UFP) side**, **USB-C to USB-C** sources may not **offer VBUS** per Type-C default current advertisement.

**Work:**

- Add two **5.1 kΩ** resistors (0402 or existing passives convention) from **CC1** and **CC2** to **GND** on the **device/sink** side (same net assignment as receptacle CC pins in `electronics_parts()` / footprint pin map—extend nets if CC pins are currently NC).
- Route on **F** (or F + via to pour) keeping clear of USB diff pairs, ESD, and strap cluster; no inline imports; match generator style in `generate_mono_split_boards.py`.
- Run through **generate + DRC gate**: 0/0 copper, monotonic unconnected/clearance; document in `LAST_CHANGES.md` when merged.

**Touchpoints:** `electronics_parts()` net map for **J_USB**, BOM/placement block near USB zone in `generate_mono_split_boards.py`; optional note in `hardware/common/MONO_SPLIT_ARCHITECTURE.md` USB-C zone list.
