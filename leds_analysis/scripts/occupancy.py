import json,sys,numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0,'scripts'); from grid import *
lab=np.load('lab_base.npy'); 
free=[]; 
for l in range(4):
    obs=lab[l]>=0; obs[:4,:]=obs[-4:,:]=True; obs[:,:4]=obs[:,-4:]=True
    free.append(ndimage.distance_transform_edt(~obs)*RES)
free=np.array(free)
via_ok=(free>=VIA_CLR).all(0)
np.save('free.npy',free)
def cap(g): return max(0,int((g-0.1+1e-9)//0.2))
def cut(name,x0,y0,x1,y1):
    n=int(max(abs(x1-x0),abs(y1-y0))/RES)+1; X=np.linspace(x0,x1,n); Y=np.linspace(y0,y1,n)
    I=np.clip((X/RES).astype(int),0,W-1); J=np.clip((Y/RES).astype(int),0,H-1)
    out={}
    for l in range(4):
        occ=lab[l,J,I]>=0; ivs=[]; k=0
        while k<n:
            if not occ[k]:
                s=k
                while k<n and not occ[k]: k+=1
                g=(k-s)*RES; ivs.append((round(float(X[s] if x0!=x1 else Y[s]),2),round(g,2),cap(g)))
            else: k+=1
        out[LAY[l]]=dict(total_tracks=sum(c for *_,c in ivs),widest=max([g for _,g,_ in ivs],default=0),n_gaps=len(ivs))
    vi=via_ok[J,I]; out['through_via_ok_len_mm']=round(float(vi.sum()*RES*(np.hypot(x1-x0,y1-y0)/max(n-1,1))/RES),2)
    print(name,json.dumps(out)); return out
cuts={
 'U1 west face x=41.8 y5.5..14.5':(41.8,5.5,41.8,14.5),
 'U1 south face y=14.4 x41.5..50.5':(41.5,14.4,50.5,14.4),
 'U1 east face x=50.2 y5.5..14.5':(50.2,5.5,50.2,14.5),
 'West of U1 to USB x=30 y2..26':(30,2,30,26),
 'East to XLAT x=58 y1..30':(58,1,58,30),
 'South corridor y=20 x28..60':(28,20,60,20),
 'South corridor y=35 x28..60':(28,35,60,35),
 'Towards power y=45 x10..60':(10,45,60,45),
 'Reserve/serial y=66 x10..60':(10,66,60,66),
}
res={k:cut(k,*v) for k,v in cuts.items()}
json.dump(res,open('cuts.json','w'))
# images
for l in range(4):
    f,ax=plt.subplots(figsize=(16,12.5))
    capm=np.floor(np.clip(2*free[l]-0.1,0,None)/0.2)
    im=ax.imshow(np.minimum(capm,10),extent=(0,190,148,0),cmap='magma',vmin=0,vmax=10,interpolation='nearest')
    plt.colorbar(im,ax=ax,label='# of 0.1mm/0.1mm tracks fitting through local free gap (2*dist-0.1)/0.2, capped 10',shrink=0.7)
    for k,(x0,y0,x1,y1) in cuts.items(): ax.plot([x0,x1],[y0,y1],'c-',lw=1)
    ax.set_title(f'{LAY[l]}.Cu free-channel capacity (white=wide open); cyan = analysed cuts'); f.savefig(f'img/occupancy_{LAY[l]}.png',dpi=150,bbox_inches='tight'); plt.close(f)
f,ax=plt.subplots(figsize=(14,7))
ax.imshow(np.dstack([via_ok*0.2+0.8*(free[1]<0.2),via_ok*1.0,via_ok*0.2+0.8*(free[2]<0.2)]),extent=(0,190,148,0),interpolation='nearest')
ax.set_xlim(25,80); ax.set_ylim(30,0)
ax.set_title('Through-via legality (green = 0.45/0.2 via fits w/ 0.1 clr on F+In1+In2+B); red=In1 copper, blue=In2 copper')
for fp in json.load(open('geom.json'))['fps']:
    if 25<fp['x']<80 and fp['y']<30:
        for p in fp['court']: ax.add_patch(plt.Polygon(p,fill=False,ec='w',lw=0.6))
        ax.text(fp['x'],fp['y'],fp['ref'],color='w',fontsize=6,ha='center')
f.savefig('img/via_legality_u1.png',dpi=220,bbox_inches='tight')
