import pcbnew,json,sys
b=pcbnew.LoadBoard(sys.argv[1]); out={'fps':[]}
bb=b.GetBoardEdgesBoundingBox(); out['edge']=[pcbnew.ToMM(bb.GetX()),pcbnew.ToMM(bb.GetY()),pcbnew.ToMM(bb.GetWidth()),pcbnew.ToMM(bb.GetHeight())]
for f in b.GetFootprints():
    if sys.argv[3] and not any(f.GetReference().startswith(p) for p in sys.argv[3].split(',')): continue
    p=f.GetPosition()
    out['fps'].append({'ref':f.GetReference(),'val':f.GetValue(),'fp':str(f.GetFPID().GetLibItemName()),'x':pcbnew.ToMM(p.x),'y':pcbnew.ToMM(p.y),'rot':f.GetOrientationDegrees(),'layer':f.GetLayerName(),
      'pads':[{'n':pd.GetNumber(),'net':pd.GetNetname(),'x':pcbnew.ToMM(pd.GetPosition().x),'y':pcbnew.ToMM(pd.GetPosition().y)} for pd in f.Pads()]})
json.dump(out,open(sys.argv[2],'w'))
