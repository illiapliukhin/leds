"""Final stage for gen_pcb.py: routes.json (router polylines, every bend filleted with a tangent arc), GND stitching vias,
GND pours on In2.Cu and B.Cu (thermal-relief pad connections), zone fill."""
import json, os, math
import pcbnew
from pcbnew import VECTOR2I, FromMM as M
H = os.path.dirname(os.path.abspath(__file__))

def finish(B, info):
    import gen_pcb as g
    R = json.load(open(os.path.join(H, 'routes.json')))
    ov = json.load(open(os.path.join(H, 'fillet_r.json'))) if os.path.exists(os.path.join(H, 'fillet_r.json')) else {}
    for k, p in enumerate(R['paths']):
        pts = [tuple(q) for q in p['pts']]
        r = ov.get(str(k), 3 * p['w'])
        B.path(pts, [p['w']] * (len(pts) - 1), p['layer'], p['net'], r=r)
    for v in R['vias']: B.via((v[0], v[1]), v[2])
    for (x, y) in R.get('stitch', []): B.via((x, y), 'GND')
    b = B.b
    for layer in (pcbnew.In2_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(B.net('GND'))
        ol = z.Outline(); ol.NewOutline()
        for (x, y) in ((0, 0), (g.S, 0), (g.S, g.S), (0, g.S)): ol.Append(M(x), M(y))
        z.SetLocalClearance(M(0.25)); z.SetMinThickness(M(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(M(0.3)); z.SetThermalReliefSpokeWidth(M(0.3))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetZoneName('GND_' + ('In2' if layer == pcbnew.In2_Cu else 'B'))
        b.Add(z)
    filler = pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
