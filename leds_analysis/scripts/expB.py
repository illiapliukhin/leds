import json,sys,time,numpy as np,pickle
sys.path.insert(0,'scripts'); from grid import *
import os
D=json.load(open(os.environ.get('GEOM','geom.json'))); R=json.load(open(os.environ.get('DRCF','drc.json')))
tag=sys.argv[1]; viac=float(sys.argv[2]); lc=tuple(float(x) for x in sys.argv[3].split(','))
order=['XTAL_P','XTAL_N','USB_D_P_MCU','USB_D_N_MCU','USB_D_P','USB_D_N','ROW_A0','ROW_A1','ROW_A2','ROW_A3','DEC_A_EN_N','DEC_B_EN_N','ROW_XLAT_OE_N',
 'IMU_SDA','IMU_SCL','IMU_INT1','LED_CLK','LED_SDI','LED_LE','LED_OE_N','LED_EN','LED_LOGIC_EN','AUDIO_EN','CHIP_PU','GPIO0_BOOT','AON_3V3','GND']
if len(sys.argv)>4 and sys.argv[4]=='rev': order=order[:-2][::-1]+order[-2:]
if len(sys.argv)>4 and sys.argv[4]=='hard': order=['LED_SDI','ROW_A1','AON_3V3']+[o for o in order if o not in ('LED_SDI','ROW_A1','AON_3V3')]
if len(sys.argv)>5 and sys.argv[4]=='file': order=json.load(open(sys.argv[5]))
un=unconnected_nets(R); order=[o for o in order if o in un]+[n for n in un if n not in order]
B=Board(D); B.newvias={}; allp={}; summ={}
for n in order:
    ok,fail,paths=B.route_net(n,viacost=viac,layercost=lc); allp[n]=paths; summ[n]=(ok,fail)
    print(n,ok,fail,flush=True)
pickle.dump(allp,open(f'routes_{tag}.pkl','wb')); json.dump(summ,open(f'summ_{tag}.json','w'))
print('TOTAL fail joins',sum(f for o,f in summ.values()))
