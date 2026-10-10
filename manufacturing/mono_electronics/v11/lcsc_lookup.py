import json,urllib.request,time,re,sys
API="https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
def q(kw,n=25):
    r=urllib.request.Request(API,data=json.dumps({"keyword":kw,"currentPage":1,"pageSize":n}).encode(),headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
    for i in range(3):
        try: return json.load(urllib.request.urlopen(r,timeout=30))['data']['componentPageInfo']['list'] or []
        except Exception as e: time.sleep(2)
    return []
# (value,footprint) -> (keyword, must-match regex on model, package hint)
SPEC={
 ('1.82k','R_0402_1005Metric'):('1.82kΩ 0402','', '0402'),
 ('100k','R_0402_1005Metric'):('100kΩ 0402 1%','','0402'),
 ('100n','C_0402_1005Metric'):('100nF 0402 16V','','0402'),
 ('100nF','C_0402_1005Metric'):('100nF 0402 16V','','0402'),
 ('10k','R_0402_1005Metric'):('10kΩ 0402 1%','','0402'),
 ('10k 1%','R_0402_1005Metric'):('10kΩ 0402 1%','','0402'),
 ('10p','C_0402_1005Metric'):('10pF 0402 50V C0G','','0402'),
 ('10u','C_0805_2012Metric'):('10uF 0805 25V','','0805'),
 ('120R','R_0603_1608Metric'):('120Ω 0603 1%','','0603'),
 ('18k','R_0402_1005Metric'):('18kΩ 0402 1%','','0402'),
 ('1k','R_0402_1005Metric'):('1kΩ 0402 1%','','0402'),
 ('1u','C_0402_1005Metric'):('1uF 0402 10V','','0402'),
 ('1u','C_0603_1608Metric'):('1uF 0603 25V','','0603'),
 ('2.2k','R_0402_1005Metric'):('2.2kΩ 0402 1%','','0402'),
 ('22R','R_0402_1005Metric'):('22Ω 0402 1%','','0402'),
 ('22u','C_0805_2012Metric'):('22uF 0805 10V','','0805'),
 ('24nH','L_0402_1005Metric'):('24nH 0402 inductor','','0402'),
 ('33R','R_0402_1005Metric'):('33Ω 0402 1%','','0402'),
 ('4.7k','R_0402_1005Metric'):('4.7kΩ 0402 1%','','0402'),
 ('4.7u','C_0402_1005Metric'):('4.7uF 0402 6.3V','','0402'),
 ('47k','R_0402_1005Metric'):('47kΩ 0402 1%','','0402'),
 ('5.1k','R_0402_1005Metric'):('5.1kΩ 0402 1%','','0402'),
 ('600R','R_0402_1005Metric'):('620Ω 0402 1%','','0402'),
 ('681k','R_0402_1005Metric'):('681kΩ 0402 1%','','0402'),
 ('91k','R_0402_1005Metric'):('91kΩ 0402 1%','','0402'),
 ('53398-0371',None):('533980371','53398-?0371',''),
 ('74HC154',None):('74HC154PW','74HC154PW',''),
 ('AO3403',None):('AO3403','^AO3403$',''),
 ('BMI270',None):('BMI270','BMI270',''),
 ('BQ25185',None):('BQ25185','BQ25185',''),
 ('DFE201612E-R47M',None):('DFE201612E-R47M','DFE201612E-R47M',''),
 ('ESP32-S3FN8',None):('ESP32-S3FN8','^ESP32-S3FN8$',''),
 ('FFC_40P_050_COL',None):('FH12-40S-0.5SH','FH12-40S-0\\.5SH',''),
 ('FFC_40P_050_ROW',None):('FH12-40S-0.5SH','FH12-40S-0\\.5SH',''),
 ('KMR2',None):('KMR221G','KMR2',''),
 ('L327S400H11L',None):('X322540MSB4SI','',''),
 ('MA-HFA381-H13-1AF',None):('MA-HFA381','HFA381',''),
 ('MAX17048G+T10',None):('MAX17048G+T10','MAX17048G',''),
 ('MBI5124GP-B',None):('MBI5124','MBI5124',''),
 ('NTC 10k B3435','R_0402_1005Metric'):('NTC 10kΩ 0402 3435','','0402'),
 ('PESD3V3S2UT',None):('PESD3V3S2UT','PESD3V3S2UT',''),
 ('SM06B-SRSS-TB',None):('SM06B-SRSS-TB','SM06B-SRSS-TB',''),
 ('SM712',None):('SM712','SM712',''),
 ('SN74LV125A',None):('SN74LV125APWR','SN74LV125APW',''),
 ('SN74LVC8T245RHLR',None):('SN74LVC8T245RHLR','SN74LVC8T245RHL',''),
 ('THVD1406DR',None):('THVD1406DR','THVD1406',''),
 ('TLV9001IDCKR',None):('TLV9001IDCKR','TLV9001IDCK',''),
 ('TPS22917',None):('TPS22917DBVR','TPS22917DBV',''),
 ('TPS63802DLAR',None):('TPS63802DLAR','TPS63802',''),
 ('TPS7A2033',None):('TPS7A2033PDBVR','TPS7A2033',''),
 ('USB4105',None):('USB4105-GF-A','USB4105',''),
 ('USBLC6-2SC6',None):('USBLC6-2SC6','USBLC6-2SC6',''),
}
DNP={'AON_3V3','GND','M2.5','TERM'}
M=json.load(open(sys.argv[1]))
import collections
g=collections.defaultdict(list)
for m in M: g[(m['value'],m['footprint'])].append(m['reference'])
rows=[]
for (val,fp),refs in sorted(g.items()):
    if val in DNP: rows.append(dict(value=val,footprint=fp,refs=refs,qty=len(refs),lcsc='',note='not assembled (test pad / mounting hole / solder jumper)')); continue
    sp=SPEC.get((val,fp)) or SPEC.get((val,None))
    kw,rx,pk=sp
    L=q(kw)
    def ok(c):
        mdl=c.get('componentModelEn') or ''
        if rx and not re.search(rx,mdl,re.I): return False
        if pk and pk not in (c.get('componentSpecificationEn') or ''): return False
        return True
    C=[c for c in L if ok(c)]
    C.sort(key=lambda c:(c.get('componentLibraryType')!='base', -(c.get('stockCount') or 0)))
    if not C: rows.append(dict(value=val,footprint=fp,refs=refs,qty=len(refs),lcsc='',note=f'NOT FOUND on JLCPCB/LCSC (search "{kw}")')); print('MISS',val); continue
    c=C[0]; pr=c.get('componentPrices') or []
    def price(n):
        for p in pr:
            if p['startNumber']<=n<=(p['endNumber'] if p['endNumber']>0 else 10**9): return p['productPrice']
        return pr[-1]['productPrice'] if pr else None
    note=''
    if (c.get('stockCount') or 0)< len(refs)*50: note='LOW/NO STOCK'
    rows.append(dict(value=val,footprint=fp,refs=refs,qty=len(refs),lcsc=c['componentCode'],mpn=c.get('componentModelEn'),lib=c.get('componentLibraryType'),stock=c.get('stockCount'),p5=price(len(refs)*5),p50=price(len(refs)*50),note=note,desc=c.get('describe','')[:80]))
    print(val,c['componentCode'],c.get('componentModelEn'),c.get('componentLibraryType'),c.get('stockCount'),note)
    time.sleep(0.4)
json.dump(rows,open('bom_lookup.json','w'),indent=1)
