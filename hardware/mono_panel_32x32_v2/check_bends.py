"""Bend audit (python3.11): every junction between two copper pieces of the same net/layer that is not a pad/via end
must be tangent (direction change < 0.5 deg). Reports corner count (must be 0), arcs, segments."""
import pcbnew, math, collections
b = pcbnew.LoadBoard('mono_panel_32x32_v2.kicad_pcb')
ends = collections.defaultdict(list)
na = ns = 0
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA': continue
    s, e = t.GetStart(), t.GetEnd()
    if t.GetClass() == 'PCB_ARC':
        na += 1; c = t.GetCenter()
        def tang(p, sgn):
            vx, vy = p.x - c.x, p.y - c.y; return (-vy * sgn, vx * sgn)
        cw = -1 if t.IsCCW() is False else 1
        ds, de = tang(s, cw), tang(e, cw)
    else:
        ns += 1; ds = de = (e.x - s.x, e.y - s.y)
    key = lambda p: (t.GetLayer(), round(p.x / 1000), round(p.y / 1000))
    ends[key(s)].append(((-ds[0], -ds[1]), t)); ends[key(e)].append((de, t))
bad = 0
for k, v in ends.items():
    if len(v) != 2: continue
    (a, _), (c2, _) = v
    na_, nc = math.hypot(*a), math.hypot(*c2)
    if na_ == 0 or nc == 0: continue
    cos = -(a[0] * c2[0] + a[1] * c2[1]) / (na_ * nc)
    ang = math.degrees(math.acos(max(-1, min(1, cos))))
    if ang > 0.5: bad += 1
print('arcs', na, 'segments', ns, 'non-tangent 2-way junctions', bad)
