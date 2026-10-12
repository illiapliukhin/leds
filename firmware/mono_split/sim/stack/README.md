# 6-board stack simulation (v13)

Six QEMU ESP32-S3 instances run the real `mono_split` firmware (MONO_SIM build). `stack_sim.py` models the shared
RS-485 bus (500 kbps, half duplex, collisions, wire time), FRAME_SYNC, and the per-side PRES lines from the
physical layout and cables. `stack_view.py` is the live viewer. `render_video.py` renders frame-exact video
offline from the JSONL log: 1920x1080, 60 fps, H.264 CRF 18, preset slow, yuv420p, +faststart.

    ./run_stack_sim.sh 3x2    # or 6x1. Paths assume the box layout (/workspace/sim/{qemu_path,flash_qemu.bin,venv})
    python render_video.py run_3x2.jsonl out.mp4 --t0 10 --t1 90

## Real panel geometry in the viewer

The panels are butted edge to edge with no gap. Geometry comes from `hardware/mono_panel_32x32/mono_panel_32x32.kicad_pcb`:

| item | value |
|---|---|
| outline | 166.7 x 166.7 mm |
| LED pitch | 2.54 mm (32 x 32 NCD0603W1, grid 78.74 mm, centred) |
| outermost LED centre to edge | 44.005 mm (left/top), 44.03 mm (right/bottom) |
| LED pitch across a butted seam | 44.03 + 44.005 = **88.035 mm**, which is 34.7x the in-panel pitch (85.5 mm too long) |
| margin needed for a seamless seam | pitch/2 = **1.27 mm**, which means an 81.28 mm panel outline (or keep 166.7 mm and use a 5.209 mm pitch with a 2.605 mm margin) |

Lattice variant for comparison: 5.2 mm pitch with margins of 18.4/18.4 mm (x) and 13.0/36.2 mm (y). That gives seams of
36.8 mm and 49.1 mm, so it is not seamless either.

The 148 x 99.5 mm electronics boards and the stacking cables are drawn behind the panels, seen through a
translucent panel. The ports sit on the electronics board edge, 9.35 mm (long side) or 33.6 mm (short side)
inside the panel edge. The shortest cable between facing ports is therefore 18.7 mm (E-W) to 67.2 mm (N-S), and the
specified 100 mm cable covers every rotation.

## Unplug/replug regression (`regress_stack.sh [rounds]`)

The test runs headless on its own ports, so the live sim on :4 is untouched. For each layout (3x2 and 6x1) and each board position 0–5:
1. Unplug the board.
2. Every remaining connected segment must re-form: one leader, unique tiles, the tile map an isometry of the physical layout (pairwise grid distances and rotation offset), and the canvas equal to the tile bounding box. Fresh reports after the unplug are required.
3. Replug the board.
4. All 6 boards must re-form under a single leader.

Results go to `regress/<layout>_<round>.json`. Run of 2026-10-11: 4 rounds x 2 layouts x 6 positions = **48/48 PASS**. Split re-forms in 5.5–15.3 s and merge in 5.8–15.5 s (QEMU time scale).

The split/merge fixes in `main/stack.c`:
- A leader beacons LEADER before probing each member, so a merging higher-ID leader hears it and steps down instead of probing concurrently.
- Members that answer no token during discovery are dropped. These are boards that ended up on the other half of a split.
- Discovery is validated (all members placed, no overlapping tiles, no foreign leader probing at the same time) and retried with a random back-off.
- A HELLO received during discovery adds the board to the member list.
- The leader records the PRES highs it sees itself, because the bus does not echo its own SEEN messages back to it.

## Showcase demos and presentation videos

`main/patterns.c` holds three full-8-bit generative patterns. The single-panel demos (`demo vyshyvanka|aurora|kinetic`) and the stack canvas (`stack demo vyshyvanka|aurora|kinetic`) both use them:
- **vyshyvanka**: cross-stitch ornaments on a 16×16 repeat tile, mirrored 8 ways (Alatyr star, nested rhombuses, oblique crosses, tree of life). They have running zigzag borders and appear stitch by stitch, then unpick. Brightness stands in for thread colour: red thread is 1.0, black thread 0.42, linen 0.035. A glow pulse runs through the red thread.
- **aurora**: three curtains with rays, flow shimmer and twinkling stars.
- **kinetic**: 18 s segments that cross-fade into each other: rotating moiré, tunnel, a Lissajous ribbon with a trail, and three-source ripples.

`stack_sim.py --show vyshyvanka:100,aurora:90,kinetic:95,vyshyvanka:0` forms the stack and runs the list. `present.py` renders a presentation video from the logged scan stream:
- Real full-bleed panel geometry (160 mm, 5.0 mm pitch, LEDs 2.5 mm from the edge, seamless when butted), gamma 2.2 display, two-radius glow, floor reflection, title cards.
- Brightness is normalised to the firmware's full-scale duty.
- The scan tap is sampled at about 12–15 Hz per board in QEMU, so frames between samples are linearly interpolated.

The stack viewer (`stack_view.py`) also uses the full-bleed geometry now.

### Frame-exact showcase rendering (no QEMU jitter)

`host/host_render.c` compiles the same `main/patterns.c` natively:

    gcc -O2 -I../../main host/host_render.c ../../main/patterns.c -lm -o host_render

It runs on a fixed 60 fps simulated clock (frame n at t = n/60). Each frame is quantised like `render_tile` (8-bit level) and mapped through the firmware gamma LUT (`build_gamma`, γ 2.2) to the BCM code, so there are no dropped or repeated frames. `present.py --raw W H` renders those frames 1:1 at 60 fps. `render_showcase.sh` is the 2026-10-11 run that produced the vyshyvanka (3×2, 90 s), aurora (3×2, 85 s) and kinetic (single panel, 81 s) videos at 2560×1440 60 fps, CRF 15, plus the 1080p chat versions.

### Large stacks (2026-10-11)

- **Ping period:** the leader pings each member every min(150 ms, T_MEMBER_LOST / (2·(N−1))), so every member is pinged at least twice per loss window. Before this, with 4 or more followers a member was declared lost after 400 ms while its turn came round only every N × 150 ms.
- **Table sizes:** MAXB went from 16 to 128 boards and the edge table from 64 to 256 edges. All tables together take about 6 KB of RAM. The stack task stack is now 10 KB and the stream task stack 6 KB.
- **Chunked messages:** the 8-bit frame length field is unchanged. LEADER member lists go out in chunks of 60 ids and MAP in chunks of 34 tiles, and followers apply the map when the last chunk arrives.
- **Regression:** 3×2 and 6×1, every position: PASS. 5×4 (20 boards, more than the old limit of 16): formed in 33 s, and unplug/replug of boards 0 and 1 passed.
- **10×10 was not run:** 100 QEMU instances need about 9 GB of RAM and about 12× more CPU than this 8-core box has.
