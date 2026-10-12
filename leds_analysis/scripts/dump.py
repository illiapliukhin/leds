import pcbnew, json, sys
b = pcbnew.LoadBoard(sys.argv[1])
MM = 1e-6
L = {pcbnew.F_Cu:'F', pcbnew.In1_Cu:'In1', pcbnew.In2_Cu:'In2', pcbnew.B_Cu:'B'}
def polys(ps):
    out=[]
    for i in range(ps.OutlineCount()):
        o=ps.Outline(i); out.append([(o.CPoint(j).x*MM,o.CPoint(j).y*MM) for j in range(o.PointCount())])
    return out
D={'tracks':[],'vias':[],'pads':[],'zones':[],'fps':[],'edge':[]}
for t in b.GetTracks():
    if t.GetClass()=='PCB_VIA':
        D['vias'].append(dict(x=t.GetPosition().x*MM,y=t.GetPosition().y*MM,d=t.GetWidth(pcbnew.F_Cu)*MM,drill=t.GetDrillValue()*MM,net=t.GetNetname(),locked=t.IsLocked()))
    elif t.GetClass()=='PCB_TRACK':
        D['tracks'].append(dict(x1=t.GetStart().x*MM,y1=t.GetStart().y*MM,x2=t.GetEnd().x*MM,y2=t.GetEnd().y*MM,w=t.GetWidth()*MM,layer=L.get(t.GetLayer(),'?'),net=t.GetNetname(),locked=t.IsLocked()))
    else:
        print('other',t.GetClass())
for fp in b.GetFootprints():
    r=fp.GetReference()
    cy=fp.GetCourtyard(pcbnew.F_CrtYd if not fp.IsFlipped() else pcbnew.B_CrtYd)
    D['fps'].append(dict(ref=r,x=fp.GetPosition().x*MM,y=fp.GetPosition().y*MM,rot=fp.GetOrientationDegrees(),side='B' if fp.IsFlipped() else 'F',court=polys(cy),locked=fp.IsLocked(),value=fp.GetValue()))
    for p in fp.Pads():
        for lid,ln in L.items():
            if p.IsOnLayer(lid) and p.FlashLayer(lid):
                ps=pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(ps,lid,0,5000,pcbnew.ERROR_INSIDE)
                D['pads'].append(dict(ref=r,num=p.GetNumber(),net=p.GetNetname(),layer=ln,poly=polys(ps),x=p.GetPosition().x*MM,y=p.GetPosition().y*MM))
for z in b.Zones():
    for lid,ln in L.items():
        if z.IsOnLayer(lid):
            D['zones'].append(dict(net=z.GetNetname(),layer=ln,outline=polys(z.Outline()),fill=polys(z.GetFilledPolysList(lid)) if z.HasFilledPolysForLayer(lid) else [],keepout=z.GetIsRuleArea()))
for d in b.GetDrawings():
    if d.GetLayer()==pcbnew.Edge_Cuts:
        D['edge'].append((d.GetStart().x*MM,d.GetStart().y*MM,d.GetEnd().x*MM,d.GetEnd().y*MM,d.GetShapeStr()))
json.dump(D,open(sys.argv[2],'w'))
print({k:len(v) for k,v in D.items()})
