import pcbnew,sys
src,dst,fix=sys.argv[1],sys.argv[2],sys.argv[3]=='1'
b=pcbnew.LoadBoard(src); fp=b.FindFootprintByReference('U1')
m={'44':'ROW_A0','45':'ROW_A1','43':'ROW_A2','23':'AUDIO_EN','24':'','27':'','48':'','11':'','32':''}
for p in fp.Pads():
    if p.GetNumber() in m:
        n=m[p.GetNumber()]; print(p.GetNumber(),p.GetNetname(),'->',n)
        if n: p.SetNet(b.FindNet(n))
        else: p.SetNetCode(0)
if fix:
    for t in list(b.GetTracks()):
        if t.GetNetname()=='AON_3V3' and ((t.GetClass()=='PCB_VIA' and abs(pcbnew.ToMM(t.GetPosition().x)-43.5)<0.01 and abs(pcbnew.ToMM(t.GetPosition().y)-9.2)<0.01) or (t.GetClass()=='PCB_TRACK' and t.GetLayer()==pcbnew.In1_Cu and abs(pcbnew.ToMM(t.GetStart().y)-9.2)<0.01 and abs(pcbnew.ToMM(t.GetEnd().y)-9.2)<0.01 and min(pcbnew.ToMM(t.GetStart().x),pcbnew.ToMM(t.GetEnd().x))<44)): b.Remove(t)
b.Save(dst)
