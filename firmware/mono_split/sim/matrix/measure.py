import socket,time,sys,statistics as st,json
# connects to QEMU UART, runs "demo smiley" (static image), collects N snapshots and reports
# per-LED brightness variance (nominal row period), OE-time spread, rows that are partial/empty
N=int(sys.argv[1]) if len(sys.argv)>1 else 120; RP=78
s=socket.create_connection(('127.0.0.1',5555)); s.settimeout(0.5); buf=b''; sent=0; snaps=[]; extra=[]
t0=time.time()
while len(snaps)<N and time.time()-t0<120:
    try: buf+=s.recv(65536)
    except socket.timeout: pass
    if not sent and b'mono>' in buf: time.sleep(.3); s.sendall(b'demo smiley\r\n'); sent=time.time()
    while b'\n' in buf:
        l,buf=buf.split(b'\n',1); l=l.decode(errors='replace').replace('mono>','').strip()
        if not l.startswith('@F') or time.time()-sent<1.5: continue
        p=l.split(); rows=[t.split(':') for t in p[4:36]]
        snaps.append(rows); extra.append(p[36:])
lum=[]; ons=[]; partial=0
for rows in snaps:
    L=[]
    for r in rows:
        b0,o0,b1,o1=int(r[0],16),int(r[1]),int(r[2],16),int(r[3])
        if (b0 or b1) and (o0==0 or o1==0): partial+=1
        if o0: ons.append(o0)
        L+= [((o0 if b0>>x&1 else 0)+(o1 if b1>>x&1 else 0))/RP for x in range(32)]
    lum.append(L)
std=[st.pstdev([f[i] for f in lum]) for i in range(1024)]
lit=[i for i in range(1024) if st.mean(f[i] for f in lum)>0.02]
print(json.dumps({'snapshots':len(snaps),'partial_rows':partial,'oe0_us_min':min(ons),'oe0_us_max':max(ons),'oe0_us_std':round(st.pstdev(ons),2),
 'led_brightness_std_mean':round(st.mean(std[i] for i in lit),4),'led_brightness_std_max':round(max(std),4),'rel_std_pct':round(100*st.mean(std[i]/st.mean(f[i] for f in lum) for i in lit),1),'extra_last':extra[-1][:6]}))
