import json, re, numpy as np, ctypes, collections
from matplotlib.path import Path
from scipy import ndimage
RES=0.1; W=1900; H=1480; LAY=['F','In1','In2','B']
TRACK_CLR = 0.075 + 0.1 + 0.05  # half 0.15 mm track + 0.1 clearance + raster slack
VIA_CLR = 0.225 + 0.1 + 0.05
EDGE=0.3+0.05
import pathlib as _pathlib

_lib_path = _pathlib.Path(__file__).resolve().with_name("libastar.so")
lib = ctypes.CDLL(str(_lib_path))
lib.route.restype=ctypes.c_int
xs=(np.arange(W)+0.5)*RES; ys=(np.arange(H)+0.5)*RES
class Board:
    def __init__(s,D,skip=lambda kind,o:False):
        s.D=D; nets=sorted({t['net'] for t in D['tracks']}|{v['net'] for v in D['vias']}|{p['net'] for p in D['pads']})
        s.nid={n:i for i,n in enumerate(nets)}; s.names=nets
        s.lab=np.full((4,H,W),-1,np.int16)
        for t in D['tracks']:
            if skip('track',t): continue
            s.seg(LAY.index(t['layer']),t['x1'],t['y1'],t['x2'],t['y2'],t['w']/2,s.nid[t['net']])
        for v in D['vias']:
            if skip('via',v): continue
            for l in range(4): s.seg(l,v['x'],v['y'],v['x'],v['y'],v['d']/2,s.nid[v['net']])
        s.padcells=collections.defaultdict(list)
        for p in D['pads']:
            l=LAY.index(p['layer'])
            for poly in p['poly']:
                a=np.array(poly); x0,y0=a.min(0); x1,y1=a.max(0)
                i0,i1=max(int(x0/RES)-1,0),min(int(x1/RES)+2,W); j0,j1=max(int(y0/RES)-1,0),min(int(y1/RES)+2,H)
                X,Y=np.meshgrid(xs[i0:i1],ys[j0:j1]); m=Path(a).contains_points(np.c_[X.ravel(),Y.ravel()]).reshape(X.shape)
                sub=s.lab[l,j0:j1,i0:i1]; sub[m]=s.nid[p['net']]
                s.padcells[(p['ref'],p['num'])].append((l,j0,i0,m))
    def seg(s,l,x1,y1,x2,y2,r,val):
        i0=max(int((min(x1,x2)-r)/RES)-1,0); i1=min(int((max(x1,x2)+r)/RES)+2,W)
        j0=max(int((min(y1,y2)-r)/RES)-1,0); j1=min(int((max(y1,y2)+r)/RES)+2,H)
        X,Y=np.meshgrid(xs[i0:i1],ys[j0:j1]); dx,dy=x2-x1,y2-y1; L2=dx*dx+dy*dy
        t=np.clip(((X-x1)*dx+(Y-y1)*dy)/L2,0,1) if L2>0 else 0
        d=np.hypot(X-(x1+t*dx),Y-(y1+t*dy)); sub=s.lab[l,j0:j1,i0:i1]; sub[d<=r]=val
    def dist(s,net):
        n=s.nid[net]; out=np.empty((4,H,W),np.float32)
        for l in range(4):
            obs=(s.lab[l]>=0)&(s.lab[l]!=n)
            obs[:int(EDGE/RES)+1,:]=obs[-int(EDGE/RES)-1:,:]=True; obs[:,:int(EDGE/RES)+1]=obs[:,-int(EDGE/RES)-1:]=True
            out[l]=ndimage.distance_transform_edt(~obs)*RES
        return out
    def components(s,net):
        n=s.nid[net]; own=(s.lab==n); comp=np.zeros((4,H,W),np.int32); nxt=1; parent={}
        for l in range(4):
            lb,k=ndimage.label(own[l],structure=np.ones((3,3)))
            comp[l][lb>0]=lb[lb>0]+nxt-1; nxt+=k
        parent={i:i for i in range(1,nxt)}
        def f(a):
            while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
            return a
        for v in s.D['vias']:
            if v['net']!=net: continue
            j,i=int(v['y']/RES),int(v['x']/RES); ids=[comp[l,j,i] for l in range(4) if comp[l,j,i]>0]
            for a in ids[1:]: parent[f(a)]=f(ids[0])
        for v in getattr(s,'newvias',{}).get(net,[]):
            j,i=v; ids=[comp[l,j,i] for l in range(4) if comp[l,j,i]>0]
            for a in ids[1:]: parent[f(a)]=f(ids[0])
        root=np.zeros(nxt,np.int32)
        for i in range(1,nxt): root[i]=f(i)
        return np.where(comp>0,root[comp],0)
    def route_net(s,net,viacost=15.0,layercost=(1,1,1,1),commit=True,prefer_comp_of=None):
        """join all components of net; returns (#joins ok, #fail, paths)"""
        dist=s.dist(net); legal=np.ascontiguousarray((dist>=TRACK_CLR).astype(np.uint8))
        via=np.ascontiguousarray((dist>=VIA_CLR).all(0).astype(np.uint8))
        ok=fail=0; paths=[]
        while True:
            comp=s.components(net); ids=[c for c in np.unique(comp) if c>0]
            if len(ids)<=1: break
            sizes={c:(comp==c).sum() for c in ids}
            src=prefer_comp_of if prefer_comp_of else None
            # start from component containing U1 pad if possible
            start_id=max(ids,key=lambda c:sizes[c])
            if src:
                l,j0,i0,m=s.padcells[src][0]; sub=comp[l,j0:j0+m.shape[0],i0:i0+m.shape[1]][m]; sub=sub[sub>0]
                if len(sub): start_id=sub[0]
            start=np.ascontiguousarray((comp==start_id).astype(np.uint8)); goal=np.ascontiguousarray(((comp>0)&(comp!=start_id)).astype(np.uint8))
            out=np.zeros(200000,np.int32); lc=np.array(layercost,np.float32)
            P=lambda a:a.ctypes.data_as(ctypes.c_void_p)
            n=lib.route(4,H,W,P(legal),P(via),P(start),P(goal),ctypes.c_float(viacost/RES),P(lc),P(out),len(out))
            if n<0:
                fail+=1; s.failed=getattr(s,'failed',[])+[net]
                # mark remaining comps as unreachable: give up
                return ok,len(ids)-1,paths
            path=out[:n][::-1]; L=path//(H*W); r=path%(H*W); Y=r//W; X=r%W
            paths.append((L,Y,X)); ok+=1
            nid=s.nid[net]
            for k in range(n):
                s.lab[L[k],Y[k],X[k]]=nid
                if k>0 and L[k]==L[k-1]: s.seg(L[k],(X[k-1]+.5)*RES,(Y[k-1]+.5)*RES,(X[k]+.5)*RES,(Y[k]+.5)*RES,0.06,nid)
                if k>0 and L[k]!=L[k-1]:
                    s.newvias=getattr(s,'newvias',{}); s.newvias.setdefault(net,[]).append((Y[k],X[k]))
                    for l in range(4): s.seg(l,(X[k]+.5)*RES,(Y[k]+.5)*RES,(X[k]+.5)*RES,(Y[k]+.5)*RES,0.225,nid)
        return ok,fail,paths
def unconnected_nets(R):
    c=collections.Counter()
    for u in R['unconnected_items']: c[re.search(r'\[([^\]]+)\]',u['items'][0]['description']).group(1)]+=1
    return c
