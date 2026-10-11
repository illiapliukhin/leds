"""Netlist-driven electrical model of board -> FFC -> panel, built from the real .kicad_pcb dumps."""
import json, os, re
import cable, panels
D = os.path.dirname(os.path.abspath(__file__))
B = json.load(open(os.path.join(D, 'board_all.json')))
P = panels.load()                                                 # --panel mono32|lattice
IR = panels.ir(json.load(open(os.path.join(D, 'ir_v3.json'))))
HC154_Y = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17]   # 74HC154 Y0..Y15 pins (datasheet)
I_COL = 1.24 / 1820 * 15                                         # A per column, MBI5124 estimate

def fps(d): return {f['ref']: f for f in d['fps']}
BF, PF = fps(B), fps(P)
def padnet(f, n): return next((p['net'] for p in f['pads'] if p['n'] == str(n)), '')

def board_row_nets():
    """firmware row index -> anode net, walking decoder -> R_G -> Q_ROW gate -> drain."""
    decs = {padnet(f, 18): f for f in BF.values() if f['val'] == '74HC154'}       # E1 net -> decoder
    out, trace = [], []
    for r in range(32):
        dec = decs['DEC_A_EN_N_4V' if r < 16 else 'DEC_B_EN_N_4V']                   # firmware: r<16 -> DEC_A
        ynet = padnet(dec, HC154_Y[r & 15])
        rg = next(f for f in BF.values() if f['ref'].startswith('R_G') and ynet in [p['net'] for p in f['pads']])
        gate = next(p['net'] for p in rg['pads'] if p['net'] != ynet)
        q = next(f for f in BF.values() if f['val'] == 'AO3403' and padnet(f, 1) == gate)
        assert padnet(q, 2) == 'LED_4V1', q['ref']
        out.append(padnet(q, 3)); trace.append((dec['ref'], HC154_Y[r & 15], ynet, rg['ref'], q['ref'], padnet(q, 3)))
    return out, trace

def board_col_nets():
    """bit c of the 32-bit word (MSB shifted first) -> COL net: first chip in the SDI chain holds bits 0..15, OUTk = pin 5+k."""
    drv = [f for f in BF.values() if f['val'].startswith('MBI5124')]
    first = next(f for f in drv if padnet(f, 2) == 'LED_SDI_Y')
    second = next(f for f in drv if padnet(f, 2) == padnet(first, 22))
    return [padnet(first if c < 16 else second, 5 + c % 16) for c in range(32)], (first['ref'], second['ref'])

class Model:
    def __init__(self):
        self.row_net, self.row_trace = board_row_nets()
        self.col_net, self.chain = board_col_nets()
        self.bpin = {}
        for ref in ('J_ROW1', 'J_COL1'):
            for p in BF[ref]['pads']:
                if p['n'].isdigit(): self.bpin[p['net']] = (ref, int(p['n']))
        self.ppin_net = {(ref, int(p['n'])): p['net'] for ref in ('J_ROW', 'J_COL') for p in PF[ref]['pads'] if p['n'].isdigit()}
        self.leds = []
        for f in P['fps']:
            if f['val'] != 'NCD0603W1': continue
            an, ca = padnet(f, 2), padnet(f, 1)
            r, c = int(re.findall(r'\d+', an)[0]) - 1, int(re.findall(r'\d+', ca)[0]) - 1
            self.leds.append({'ref': f['ref'], 'x': f['x'], 'y': f['y'], 'an': an, 'ca': ca, 'row': r, 'col': c})
        self.by_nets = {(l['an'], l['ca']): i for i, l in enumerate(self.leds)}
        self.by_rc = {(l['row'], l['col']): i for i, l in enumerate(self.leds)}
        self.set_cable('B', set())

    def set_cable(self, ctype, open_board_nets):
        self.ctype, self.opens = ctype, set(open_board_nets)
        self.maps = {'J_ROW1': cable.pin_map('J_ROW1', 'J_ROW', ctype), 'J_COL1': cable.pin_map('J_COL1', 'J_COL', ctype)}

    def through_cable(self, board_net):
        if board_net in self.opens or board_net not in self.bpin: return None
        ref, pin = self.bpin[board_net]
        ppin = self.maps[ref].get(pin)
        return self.ppin_net.get(('J_ROW' if ref == 'J_ROW1' else 'J_COL', ppin)) or None

    def light(self, rows, period):
        """rows: 32 x (decoded_row, [(bits, on_samples) x 8]) from the decoded LCD_CAM stream; period = row samples.
        Expected = design intent (frame row i x COL c+1); actual = what lights through the decoded address,
        board copper, cable and panel copper. Returns (actual, expected) duty per LED and per-row (I, drop)."""
        act = [0.0] * len(self.leds); exp = [0.0] * len(self.leds); stats = []
        for i, (drow, planes) in enumerate(rows):
            an_panel = self.through_cable(self.row_net[drow]) if 0 <= drow < 32 else None
            n_lit = 0
            for bits, on in planes:
                if not bits or not on: continue
                lit_here = 0
                for c in range(32):
                    if not (bits >> c) & 1: continue
                    exp[self.by_rc[(i, c)]] += on / period
                    ca_panel = self.through_cable(self.col_net[c])
                    j = self.by_nets.get((an_panel, ca_panel)) if an_panel and ca_panel else None
                    if j is not None:
                        act[j] += on / period; lit_here += 1
                n_lit = max(n_lit, lit_here)
            i_row = n_lit * I_COL
            a, b = IR.get(str(i + 1), [0, 0])
            stats.append((i_row, i_row * (a + b)))
        return act, exp, stats
