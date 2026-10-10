import json, re, numpy as np, ctypes, collections

_ROW_IN2_NET = re.compile(r"^ROW_\d+_Y$")
from matplotlib.path import Path
from scipy import ndimage
RES=0.1; W=1900; H=1480; LAY=['F','In1','In2','B']
TRACK_CLR = 0.075 + 0.1 + 0.05  # half 0.15 mm track + 0.1 clearance + raster slack
VIA_CLR = 0.225 + 0.1 + 0.05
EDGE=0.3+0.05
POWER_TRACK_R = {"GND": 0.125, "AON_3V3": 0.10}
DEFAULT_TRACK_R = 0.075
import pathlib as _pathlib

_lib_path = _pathlib.Path(__file__).resolve().with_name("libastar.so")
lib = ctypes.CDLL(str(_lib_path))
lib.route.restype = ctypes.c_int
xs=(np.arange(W)+0.5)*RES; ys=(np.arange(H)+0.5)*RES

def track_radius(net_name: str) -> float:
    return POWER_TRACK_R.get(net_name, DEFAULT_TRACK_R)

def _track_paint_radius(track: dict) -> float:
    """Paint radius for existing copper; ROW_*_Y on In2 is a hard corridor under U1."""
    radius = track["w"] / 2
    if track.get("layer") == "In2" and _ROW_IN2_NET.match(track.get("net", "")):
        return max(radius + 0.125, TRACK_CLR)
    if track.get("hard_obstacle"):
        return max(radius + 0.125, TRACK_CLR)
    return radius

class Board:
    def __init__(s,D,skip=lambda kind,o:False):
        s.D=D; nets=sorted({t['net'] for t in D['tracks']}|{v['net'] for v in D['vias']}|{p['net'] for p in D['pads']})
        s.nid={n:i for i,n in enumerate(nets)}; s.names=nets
        s.lab=np.full((4,H,W),-1,np.int16)
        s.hard=np.zeros((4,H,W),bool)
        for t in D['tracks']:
            if skip('track',t): continue
            layer_index=LAY.index(t['layer'])
            paint_r=_track_paint_radius(t)
            s.seg(layer_index,t['x1'],t['y1'],t['x2'],t['y2'],paint_r,s.nid[t['net']])
            if t.get("hard_obstacle") or (
                t.get("layer") == "In2" and _ROW_IN2_NET.match(t.get("net", ""))
            ):
                i0=max(int((min(t['x1'],t['x2'])-paint_r)/RES)-1,0)
                i1=min(int((max(t['x1'],t['x2'])+paint_r)/RES)+2,W)
                j0=max(int((min(t['y1'],t['y2'])-paint_r)/RES)-1,0)
                j1=min(int((max(t['y1'],t['y2'])+paint_r)/RES)+2,H)
                s.hard[layer_index,j0:j1,i0:i1]=True
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
        s.base_lab=s.lab.copy()
        s.newvias={}
        s.routed_paths={}

    def reset_lab(s):
        s.lab=s.base_lab.copy()
        s.newvias={}

    def seg(s,l,x1,y1,x2,y2,r,val):
        i0=max(int((min(x1,x2)-r)/RES)-1,0); i1=min(int((max(x1,x2)+r)/RES)+2,W)
        j0=max(int((min(y1,y2)-r)/RES)-1,0); j1=min(int((max(y1,y2)+r)/RES)+2,H)
        X,Y=np.meshgrid(xs[i0:i1],ys[j0:j1]); dx,dy=x2-x1,y2-y1; L2=dx*dx+dy*dy
        t=np.clip(((X-x1)*dx+(Y-y1)*dy)/L2,0,1) if L2>0 else 0
        d=np.hypot(X-(x1+t*dx),Y-(y1+t*dy)); sub=s.lab[l,j0:j1,i0:i1]; sub[d<=r]=val

    def uncommit_net(s, net_name):
        if net_name not in s.nid:
            return
        n=s.nid[net_name]
        s.lab[s.lab==n]=s.base_lab[s.lab==n]
        s.newvias.pop(net_name, None)
        s.routed_paths.pop(net_name, None)

    def commit_path(s, net_name, path_tuple, track_r=None):
        if track_r is None:
            track_r=track_radius(net_name)
        L,Y,X=path_tuple
        nid=s.nid[net_name]
        n=len(L)
        for k in range(n):
            s.lab[L[k],Y[k],X[k]]=nid
            if k>0 and L[k]==L[k-1]:
                s.seg(L[k],(X[k-1]+.5)*RES,(Y[k-1]+.5)*RES,(X[k]+.5)*RES,(Y[k]+.5)*RES,track_r,nid)
            if k>0 and L[k]!=L[k-1]:
                s.newvias.setdefault(net_name,[]).append((Y[k],X[k]))
                for l in range(4):
                    s.seg(l,(X[k]+.5)*RES,(Y[k]+.5)*RES,(X[k]+.5)*RES,(Y[k]+.5)*RES,0.225,nid)

    def recommit_all(s, all_paths: dict):
        s.reset_lab()
        for net_name, path_list in all_paths.items():
            tr=track_radius(net_name)
            for path_tuple in path_list:
                s.commit_path(net_name, path_tuple, tr)
            s.routed_paths[net_name]=path_list

    def dist(s,net):
        n=s.nid[net]; out=np.empty((4,H,W),np.float32)
        tr=track_radius(net)
        need=max(TRACK_CLR, tr+0.1+0.05)
        for l in range(4):
            obs=(s.lab[l]>=0)&(s.lab[l]!=n)
            if getattr(s, "hard", None) is not None:
                obs=obs|s.hard[l]
            obs[:int(EDGE/RES)+1,:]=obs[-int(EDGE/RES)-1:,:]=True; obs[:,:int(EDGE/RES)+1]=obs[:,-int(EDGE/RES)-1:]=True
            out[l]=ndimage.distance_transform_edt(~obs)*RES
        return out, need

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

    def is_connected(s, net_name):
        if net_name not in s.nid:
            return True
        comp=s.components(net_name)
        ids=[c for c in np.unique(comp) if c>0]
        return len(ids)<=1

    def present_usage(s, skip_net=None):
        """Per-cell count of foreign copper (PathFinder present term)."""
        usage=np.zeros((4,H,W),np.float32)
        skip_id=s.nid.get(skip_net,-1) if skip_net else -1
        for l in range(4):
            foreign=(s.lab[l]>=0)&(s.lab[l]!=skip_id)
            usage[l]=foreign.astype(np.float32)
        return usage

    def route_net(s,net,viacost=15.0,layercost=(1,1,1,1),commit=True,prefer_comp_of=None,cellcost=None,track_r=None,max_joins=32):
        """join all components of net; returns (#joins ok, #fail, paths)"""
        if track_r is None:
            track_r=track_radius(net)
        dist, need=s.dist(net)
        if cellcost is not None:
            need_arr = need + np.clip((cellcost - 1.0) * 0.06, 0.0, 0.45).astype(np.float32)
            legal=np.ascontiguousarray((dist>=need_arr).astype(np.uint8))
        else:
            legal=np.ascontiguousarray((dist>=need).astype(np.uint8))
        via=np.ascontiguousarray((dist>=VIA_CLR).all(0).astype(np.uint8))
        ok=fail=0; paths=[]
        while True:
            if ok >= max_joins:
                comp=s.components(net)
                ids=[c for c in np.unique(comp) if c>0]
                return ok, max(len(ids)-1, 1), paths
            comp=s.components(net); ids=[c for c in np.unique(comp) if c>0]
            if len(ids)<=1: break
            sizes={c:(comp==c).sum() for c in ids}
            src=prefer_comp_of if prefer_comp_of else None
            start_id=max(ids,key=lambda c:sizes[c])
            if src and src in s.padcells:
                l,j0,i0,m=s.padcells[src][0]; sub=comp[l,j0:j0+m.shape[0],i0:i0+m.shape[1]][m]; sub=sub[sub>0]
                if len(sub): start_id=sub[0]
            start=np.ascontiguousarray((comp==start_id).astype(np.uint8))
            goal=np.ascontiguousarray(((comp>0)&(comp!=start_id)).astype(np.uint8))
            out=np.zeros(200000,np.int32); lc=np.array(layercost,np.float32)
            P=lambda a:a.ctypes.data_as(ctypes.c_void_p)
            n=lib.route(4,H,W,P(legal),P(via),P(start),P(goal),ctypes.c_float(viacost/RES),P(lc),P(out),len(out))
            if n<0:
                fail+=1
                return ok,len(ids)-1,paths
            path=out[:n][::-1]; L=path//(H*W); r=path%(H*W); Y=r//W; X=r%W
            paths.append((L,Y,X)); ok+=1
            if commit:
                s.commit_path(net,(L,Y,X),track_r)
        if commit and paths:
            s.routed_paths[net]=paths
        return ok,fail,paths

def unconnected_nets(R):
    c=collections.Counter()
    for u in R['unconnected_items']: c[re.search(r'\[([^\]]+)\]',u['items'][0]['description']).group(1)]+=1
    return c

def bump_hist_from_paths(hist, all_paths, amount=1.0):
    for net_name, path_list in all_paths.items():
        for L,Y,X in path_list:
            for k in range(len(L)):
                hist[L[k],Y[k],X[k]]+=amount
