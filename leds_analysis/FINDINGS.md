# U1 routing analysis (branch cursor/esp32-gpio-route-mono-9adf @ d04c64c2)
Tools: KiCad 10.0.7 AppImage at /workspace/.kicad10 (kicad-cli + pcbnew python3.11), scripts/ (dump, render, grid router in C).
- Baseline DRC: 73 unconnected, 0 shorts. Also 2 clearance + 2 hole_clearance errors (IMU_SDA/IMU_SCL vias vs In1 at 62.35,4.5), and 3 courtyard overlaps.
- B.Cu: 0 tracks on the whole board. F 3.7 m, In1 12.8 m, In2 9.0 m.
- ROW_01..12_Y In1 west legs: y 9.70, 11.57 ... 18.07 (0.645-0.65 pitch, 0.15 wide), x 33.4..81.7. In2 drops x 33.40..38.68. East legs y 23.5..36.85.
  Gap between lines 0.50 mm; a through via needs 0.65 mm (0.45 via) or 0.60 mm (0.40 min via). The 9.70/11.57 gap is 1.72 mm, so one via row fits at y~10.63.
- AON_3V3 via (43.5,9.2) d0.4 sits inside the U1 EP (pad 57 GND spans x43.2-48.8, y7.2-12.8). KiCad flags it only after pcbnew re-saves the file.
- U1 pads 11 (GPIO6), 32 (SPICS0 = in-package flash CS#), 44 (GPIO39/MTCK) and 45 (GPIO40/MTDO) are on net GND. The ESP32-S3 datasheet lists them as I/O, not ground.
- Greedy grid router trial (0.1 mm grid, 0.1 mm track/0.1 mm clearance, 0.45/0.2 via): it routes 68 of 73 connections, then real KiCad DRC shows 0 new shorts/clearance. Saved as trial/c1.kicad_pcb (NOT in repo).
