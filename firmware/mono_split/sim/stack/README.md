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
