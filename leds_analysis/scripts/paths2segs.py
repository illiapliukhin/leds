import pickle,json,sys
RES=0.1; LAY=['F','In1','In2','B']
allp=pickle.load(open(sys.argv[1],'rb')); segs=[]; vias=[]
for net,paths in allp.items():
    for L,Y,X in paths:
        pts=[(int(L[k]),(X[k]+.5)*RES,(Y[k]+.5)*RES) for k in range(len(L))]
        # split on layer change
        run=[pts[0]]
        def flush(run):
            if len(run)<2: return
            # merge collinear
            out=[run[0]]
            for i in range(1,len(run)-1):
                a,b,c=out[-1],run[i],run[i+1]
                d1=(round((b[1]-a[1])/RES),round((b[2]-a[2])/RES)); d2=(round((c[1]-b[1])/RES),round((c[2]-b[2])/RES))
                import math
                if d1[0]*d2[1]-d1[1]*d2[0]!=0 or d1[0]*d2[0]+d1[1]*d2[1]<0: out.append(b)
            out.append(run[-1])
            for a,b in zip(out,out[1:]): segs.append(dict(net=net,layer=LAY[a[0]],x1=a[1],y1=a[2],x2=b[1],y2=b[2]))
        for p in pts[1:]:
            if p[0]!=run[-1][0]:
                flush(run); vias.append(dict(net=net,x=p[1],y=p[2])); run=[p]
            else: run.append(p)
        flush(run)
json.dump(dict(segs=segs,vias=vias),open(sys.argv[2],'w')); print(len(segs),len(vias))
