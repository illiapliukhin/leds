import json,sys,subprocess,os
tag,viac,lc=sys.argv[1],sys.argv[2],sys.argv[3]
base=['XTAL_P','XTAL_N','USB_D_P_MCU','USB_D_N_MCU','USB_D_P','USB_D_N','ROW_A0','ROW_A1','ROW_A2','ROW_A3','DEC_A_EN_N','DEC_B_EN_N','ROW_XLAT_OE_N','IMU_SDA','IMU_SCL','IMU_INT1','LED_CLK','LED_SDI','LED_LE','LED_OE_N','LED_EN','LED_LOGIC_EN','AUDIO_EN','CHIP_PU','GPIO0_BOOT','AON_3V3','GND']
order=base; best=None
import os
for it in range(int(os.environ.get("NIT","4"))):
    open(f'order_{tag}.json','w').write(json.dumps(order))
    subprocess.run(['venv/bin/python','scripts/expB.py',f'{tag}_{it}',viac,lc,'file',f'order_{tag}.json'],stdout=open(f'expB_{tag}_{it}.log','w'))
    s=json.load(open(f'summ_{tag}_{it}.json')); fails=[n for n,(o,f) in s.items() if f>0]; tot=sum(f for o,f in s.values())
    print(it,tot,fails,flush=True)
    if tot==0: break
    order=fails+[n for n in order if n not in fails]
