import json,sys,time,copy,numpy as np,pickle
sys.path.insert(0,'scripts'); from grid import *
D=json.load(open('geom.json')); R=json.load(open('drc.json'))
t=time.time(); B=Board(D); print('raster',time.time()-t)
np.save('lab_base.npy',B.lab)
nets=unconnected_nets(R)
base=B.lab.copy(); res={}
for n in nets:
    B.lab=base.copy(); B.newvias={}
    t=time.time(); ok,fail,paths=B.route_net(n)
    vias=sum(int((np.diff(p[0])!=0).sum()) for p in paths); lay=sorted({LAY[l] for p in paths for l in set(p[0].tolist())})
    res[n]=(ok,fail,vias,lay); print(n,'joins ok',ok,'fail',fail,'vias',vias,lay,round(time.time()-t,1),flush=True)
json.dump(res,open('expA.json','w'))
