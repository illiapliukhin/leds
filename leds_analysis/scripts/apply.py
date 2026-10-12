import pcbnew,json,sys
b=pcbnew.LoadBoard(sys.argv[1]); J=json.load(open(sys.argv[2]))
L={'F':pcbnew.F_Cu,'In1':pcbnew.In1_Cu,'In2':pcbnew.In2_Cu,'B':pcbnew.B_Cu}
mm=pcbnew.FromMM
for s in J['segs']:
    t=pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(s['x1']),mm(s['y1']))); t.SetEnd(pcbnew.VECTOR2I(mm(s['x2']),mm(s['y2'])))
    t.SetWidth(mm(0.1)); t.SetLayer(L[s['layer']]); t.SetNet(b.FindNet(s['net'])); b.Add(t)
for v in J['vias']:
    t=pcbnew.PCB_VIA(b); t.SetPosition(pcbnew.VECTOR2I(mm(v['x']),mm(v['y']))); t.SetWidth(mm(0.45)); t.SetDrill(mm(0.2)); t.SetNet(b.FindNet(v['net'])); b.Add(t)
b.Save(sys.argv[3]); print('saved')
