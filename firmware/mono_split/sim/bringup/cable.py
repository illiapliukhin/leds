"""Netlist/geometry FFC check: which board pin meets which panel pin through a straight 40-way
0.5 mm FFC with FH12-40S-0.5SH bottom-contact receptacles at both ends.
Material frame of the ribbon: T (along, from board end), N (side-1 normal), B = T x N.
Conductor k sits at a fixed offset along B. At each end: bottom contact => the exposed side faces
the PCB the receptacle is soldered to. Type A = contacts exposed on the same side at both ends,
Type B = opposite sides. Result is invariant to bends/folds/twists of the cable route."""
import json,numpy as np
import os
_D=os.path.dirname(os.path.abspath(__file__))
B=json.load(open(os.path.join(_D,'board.json'))); P=json.load(open(os.path.join(_D,'panel.json')))
def fp(d,ref): return next(f for f in d['fps'] if f['ref']==ref)
def pads(f): return {int(p['n']):np.array([p['x'],-p['y'],0.0]) for p in f['pads'] if p['n'].isdigit()}
def side_out(f): return np.array([0,0,1.0]) if f['layer']=='F.Cu' else np.array([0,0,-1.0])
def mapping(bref,pref,out_b,out_p,ctype):
    fb,fpn=fp(B,bref),fp(P,pref); pb,pp=pads(fb),pads(fpn)
    cb=np.mean(list(pb.values()),0); cp=np.mean(list(pp.values()),0)
    Nb=-side_out(fb)                       # exposed side faces the board
    Np=-side_out(fpn) if ctype=='A' else side_out(fpn)
    Bb=np.cross(out_b,Nb); Bp=np.cross(-out_p,Np)
    sb={k:round(float(Bb@(v-cb)),2) for k,v in pb.items()}
    sp={round(float(Bp@(v-cp)),2):k for k,v in pp.items()}
    return {k:sp.get(s) for k,s in sb.items()}, fb, fpn
OUT_BOARD=np.array([1.0,0,0])                     # J_ROW1/J_COL1: cable exits east (arch doc)
OUT_PANEL={'J_ROW':np.array([-1.0,0,0]),'J_COL':np.array([0,-1.0,0])}  # panel: west edge / south edge (KiCad +y = 3D -y)
def pin_map(bref,pref,ctype): return mapping(bref,pref,OUT_BOARD,OUT_PANEL[pref],ctype)[0]

def main():
    res={}
    for bref,pref in (('J_ROW1','J_ROW'),('J_COL1','J_COL')):
        for t in 'AB':
            m,fb,fpn=mapping(bref,pref,OUT_BOARD,OUT_PANEL[pref],t)
            straight=all(m[k]==k for k in m); rev=all(m[k]==41-k for k in m)
            bn={int(p['n']):p['net'] for p in fb['pads'] if p['n'].isdigit()}; pn={int(p['n']):p['net'] for p in fpn['pads'] if p['n'].isdigit()}
            bad=[(k,bn[k],m[k],pn.get(m[k])) for k in range(1,33) if bn[k]!=pn.get(m[k])]
            res[f'{bref}->{pref} type{t}']={'pin1_to':m[1],'pin40_to':m[40],'straight':straight,'reversed':rev,'net_mismatches':len(bad),'first':bad[:3]}
    print(json.dumps(res,indent=1)); json.dump(res,open(os.path.join(_D,'cable_check.json'),'w'),indent=1)

if __name__=='__main__':
    main()
