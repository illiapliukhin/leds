"""Parameters of the 32x32 wire grid (all generators read this). Change PITCH etc. and re-run gen_all.sh."""
N = 32                 # rows = cols
PITCH = 10.0           # mm, LED pitch (cube layer)
RAIL_GAP = 15.0        # mm, last LED to frame rail
FRAME_W = 12.0         # mm, frame bar width
ROW_WIRE_D = 0.50      # mm, enamelled Cu (PEW/UEW), rows (anodes)
COL_WIRE_D = 0.25      # mm, enamelled Cu, columns (cathodes)
LED = 'NCD0603W1'      # 0603 white, LCSC C84265
I_LED = 0.010          # A
I_ROW = N * I_LED      # 0.32 A
LEAD_RIBBON_M = 0.50   # m, IDC ribbon tag/fan -> breakout or v15 header
FAN_MAX_M = 0.20       # m, worst fan-out pigtail (rail pad -> IDC socket)
FFC_M = 0.12           # m, v15 default FFC (option A only)
RHO_CU = 1.72e-8 * (1 + 0.00393 * 5)   # ohm*m at 25 C
SPAN = PITCH * (N - 1)                 # 310 mm LED centre to centre
WIRE_LEN = SPAN + 2 * RAIL_GAP         # 340 mm rail to rail
INNER = WIRE_LEN                       # frame window
OUTER = INNER + 2 * FRAME_W
