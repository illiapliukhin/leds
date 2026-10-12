import json,sys,os,time,pickle,numpy as np,collections
sys.path.insert(0,'scripts'); from grid import *
D=json.load(open(os.environ.get('GEOM','geom.json'))); R=json.load(open(os.environ.get('DRCF','drc.json')))
tag=sys.argv[1]; viac=1.5; lc=(1,1,1,0.9)
order=['XTAL_P','XTAL_N','USB_D_P_MCU','USB_D_N_MCU','USB_D_P','USB_D_N','ROW_A0','ROW_A1','ROW_A2','ROW_A3','DEC_A_EN_N','DEC_B_EN_N','ROW_XLAT_OE_N','IMU_SDA','IMU_SCL','IMU_INT1','LED_CLK','LED_SDI','LED_LE','LED_OE_N','LED_EN','LED_LOGIC_EN','AUDIO_EN','CHIP_PU','GPIO0_BOOT','AON_3V3','GND']
un=unconnected_nets(R); order=[o for o in order if o in un]+[n for n in un if n not in order]
B=Board(D); fixed=B.lab.copy(); routes={}; vias={}
def redraw():
    B.lab=fixed.copy(); B.newvias={}
    for n,paths in routes.items():
        nid=B.nid[n]
        for L,Y,X in paths:
            for k in range(len(L)):
                B.lab[L[k],Y[k],X[k]]=nid
                if k>0 and L[k]==L[k-1]: B.seg(L[k],(X[k-1]+.5)*RES,(Y[k-1]+.5)*RES,(X[k]+.5)*RES,(Y[k]+.5)*RES,0.06,nid)
                if k>0 and L[k]!=L[k-1]:
                    B.newvias.setdefault(n,[]).append((Y[k],X[k]))
                    for l in range(4): B.seg(l,(X[k]+.5)*RES,(Y[k]+.5)*RES,(X[k]+.5)*RES,(Y[k]+.5)*RES,0.225,nid)
queue=collections.deque(order); hist=collections.Counter(); ops=0; MAXOPS=int(os.environ.get('MAXOPS','90'))
while queue and ops<MAXOPS:
    n=queue.popleft(); ops+=1
    routes.pop(n,None); redraw()
    ok,fail,paths=B.route_net(n,viacost=viac,layercost=lc)
    if fail==0:
        routes[n]=paths; print(ops,n,'ok',flush=True); continue
    # probe on fixed-only copper
    saved=routes; routes={}; redraw(); ok2,fail2,p2=B.route_net(n,viacost=viac,layercost=lc); routes=saved
    if fail2>0:
        print(ops,n,'IMPOSSIBLE even on fixed copper',flush=True); hist[n]+=99; routes[n]=paths; continue
    redraw()
    # who conflicts: new-route nets near probe path
    newlab=B.lab.copy(); newlab[fixed>=0]=-1
    conf=collections.Counter()
    for L,Y,X in p2:
        for dy in range(-4,5):
            for dx in range(-4,5):
                yy=np.clip(Y+dy,0,H-1); xx=np.clip(X+dx,0,W-1)
                for l in range(4):
                    v=newlab[l,yy,xx]; v=v[(v>=0)&(v!=B.nid[n])]
                    for a in v: conf[B.names[a]]+=1
    victims=[c for c in conf if c in routes]
    print(ops,n,'fail -> rip',victims,flush=True)
    for v in victims: routes.pop(v,None); queue.append(v); hist[v]+=1
    routes[n]=p2   # take probe path; it may now clash only with ripped nets (removed)
redraw()
# final check: count unrouted by recomputing components
fails={}
for n in order:
    c=B.components(n); k=len([x for x in np.unique(c) if x>0])
    if k>1: fails[n]=k-1
print('REMAINING queue',list(queue),'FAILS',fails,'TOTAL',sum(fails.values()))
pickle.dump(routes,open(f'routes_{tag}.pkl','wb'))
