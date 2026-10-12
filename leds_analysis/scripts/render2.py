import os, json, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
from matplotlib.collections import LineCollection, PatchCollection
D=json.load(open(os.environ.get('GEOM','geom.json'))); R=json.load(open(os.environ.get('DRCF','drc.json')))
COL={'F':'#d62728','In1':'#2ca02c','In2':'#1f77b4','B':'#9467bd'}
ORDER=['B','In2','In1','F']
def rats():
    out=[]
    for u in R['unconnected_items']:
        a,b=u['items'][0]['pos'],u['items'][1]['pos']
        out.append(((a['x'],a['y']),(b['x'],b['y'])))
    return out
def draw(ax,layers,alpha=0.85,labels_bbox=None,ratsnest=True,hl=None,k=1.0):
    for l in [x for x in ORDER if x in layers]:
        segs=[((t['x1'],t['y1']),(t['x2'],t['y2'])) for t in D['tracks'] if t['layer']==l]
        ws=[t['w'] for t in D['tracks'] if t['layer']==l]
        ax.add_collection(LineCollection(segs,linewidths=[w*k for w in ws],colors=COL[l],alpha=alpha,capstyle='round'))
        pp=[Polygon(p,closed=True) for pd in D['pads'] if pd['layer']==l for p in pd['poly']]
        ax.add_collection(PatchCollection(pp,facecolor=COL[l],edgecolor='none',alpha=alpha))
    ax.add_collection(PatchCollection([Circle((v['x'],v['y']),v['d']/2) for v in D['vias']],facecolor='#bbbb00',edgecolor='k',linewidth=0.1))
    for f in D['fps']:
        for p in f['court']: ax.add_patch(Polygon(p,closed=True,fill=False,ec='#888',lw=0.3,ls='--'))
    if ratsnest: ax.add_collection(LineCollection(rats(),colors='orange',linewidths=0.6,linestyles='-',alpha=0.9))
    if labels_bbox:
        x0,y0,x1,y1=labels_bbox
        for f in D['fps']:
            if x0<f['x']<x1 and y0<f['y']<y1: ax.text(f['x'],f['y'],f['ref'],fontsize=5 if (x1-x0)<60 else 3,ha='center',va='center',color='k',alpha=0.8)
        if (x1-x0)<40:
            for t in D['tracks']:
                if t['layer'] in layers and x0<(t['x1']+t['x2'])/2<x1 and y0<(t['y1']+t['y2'])/2<y1 and abs(t['x2']-t['x1'])+abs(t['y2']-t['y1'])>2:
                    ax.text((t['x1']+t['x2'])/2,(t['y1']+t['y2'])/2,t['net'],fontsize=2.5,color=COL[t['layer']],ha='center')
    for e in D['edge']: ax.plot([e[0],e[2]],[e[1],e[3]],'k',lw=0.5)
def fig(layers,bbox,fn,title,dpi=300,size=None):
    x0,y0,x1,y1=bbox
    w=size or 14; h=w*(y1-y0)/(x1-x0)
    f,ax=plt.subplots(figsize=(w,max(h,3)))
    ax.set_xlim(x0,x1); ax.set_ylim(y1,y0); ax.set_aspect('equal')
    f.canvas.draw(); bb=ax.get_window_extent(); k=bb.width/f.dpi*72/(x1-x0)
    draw(ax,layers,labels_bbox=bbox,k=k)
    ax.set_title(title); ax.grid(True,lw=0.2,alpha=0.5)
    from matplotlib.lines import Line2D
    ax.legend([Line2D([0],[0],color=COL[l],lw=3) for l in layers]+[Line2D([0],[0],color='orange')],layers+['ratsnest (DRC unconnected)'],loc='upper right',fontsize=7)
    f.savefig('img/'+fn,dpi=dpi,bbox_inches='tight'); plt.close(f)
ALL=['F','In1','In2','B']; P=os.environ.get('PFX','x_')
fig(ALL,(28,0,80,26),P+'u1_all.png',os.environ.get('TTL','')+' U1 region, all layers',dpi=350,size=14)
fig(ALL,(0,0,130,100),P+'paths_all.png',os.environ.get('TTL','')+' U1->targets, all layers',dpi=250,size=16)
for l in ALL: fig([l],(28,0,80,26),P+f'u1_{l}.png',os.environ.get('TTL','')+f' U1 region {l}',dpi=300,size=12)
