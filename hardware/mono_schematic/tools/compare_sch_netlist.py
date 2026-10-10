#!/usr/bin/env python3
"""Real schematic-vs-PCB check: kicad-cli netlist exported from the schematic vs. pad nets on the PCB.
Nets are compared as sets of (ref,pad) groups, so a net name is not required to match - connectivity is."""
import json,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(Path(__file__).parent))
from extract_pcb_components import extract_board
xmlp=sys.argv[1]
t=ET.parse(xmlp).getroot()
sch={}
for n in t.find('nets'):
    nodes=frozenset((nd.get('ref'),nd.get('pin')) for nd in n.findall('node'))
    sch[n.get('name').lstrip('/')]=nodes
sch_refs={c.get('ref') for c in t.find('components')}
pcb={}
fps=extract_board(ROOT/'hardware/mono_electronics/mono_electronics.kicad_pcb')
for f in fps:
    for p,n in f.pad_nets.items(): pcb.setdefault(n,set()).add((f.reference,p))
pcb={k:frozenset(v) for k,v in pcb.items()}
pcb_refs={f.reference for f in fps}
# map pad->net both sides
def inv(d): return {node:k for k,v in d.items() for node in v}
ps,ss=inv(pcb),inv(sch)
diffs=[]
for node,net in ps.items():
    sn=ss.get(node)
    if sn is None: diffs.append(f'{node} pcb={net} sch=<unconnected>'); continue
    if pcb[net]!=sch[sn]: diffs.append(f'{node} pcb={net}({len(pcb[net])}) sch={sn}({len(sch[sn])})')
for node,net in ss.items():
    if node not in ps and len(sch[net])>1: diffs.append(f'{node} sch={net} pcb=<no net>')
rep={'pcb_refs':len(pcb_refs),'sch_refs':len(sch_refs),'refs_only_pcb':sorted(pcb_refs-sch_refs),'refs_only_sch':sorted(sch_refs-pcb_refs),'pin_differences':len(diffs),'examples':diffs[:40]}
(ROOT/'hardware/mono_schematic/reports/sch_netlist_vs_pcb.json').write_text(json.dumps(rep,indent=2))
print(json.dumps({k:v for k,v in rep.items() if k!='examples'},indent=1)); print('\n'.join(diffs[:15]))
sys.exit(1 if diffs or rep['refs_only_pcb'] or rep['refs_only_sch'] else 0)
