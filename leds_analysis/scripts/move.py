import pcbnew,sys
src,dst,x,y,rot,fix=sys.argv[1],sys.argv[2],float(sys.argv[3]),float(sys.argv[4]),float(sys.argv[5]),sys.argv[6]=='1'
b=pcbnew.LoadBoard(src); fp=b.FindFootprintByReference('U1')
fp.SetOrientationDegrees(rot); fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
if fix:
    for t in list(b.GetTracks()):
        p=t.GetPosition(); 
        if t.GetNetname()=='AON_3V3' and ((t.GetClass()=='PCB_VIA' and abs(pcbnew.ToMM(p.x)-43.5)<0.01 and abs(pcbnew.ToMM(p.y)-9.2)<0.01) or
           (t.GetClass()=='PCB_TRACK' and t.GetLayer()==pcbnew.In1_Cu and abs(pcbnew.ToMM(t.GetStart().y)-9.2)<0.01 and abs(pcbnew.ToMM(t.GetEnd().y)-9.2)<0.01 and min(pcbnew.ToMM(t.GetStart().x),pcbnew.ToMM(t.GetEnd().x))<44)):
            print('removed',t.GetClass(),pcbnew.ToMM(t.GetStart().x),pcbnew.ToMM(t.GetEnd().x)); b.Remove(t)
b.Save(dst)
