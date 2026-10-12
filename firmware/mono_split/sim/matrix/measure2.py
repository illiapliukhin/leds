import socket,time,sys,statistics as st,json
N=int(sys.argv[1]) if len(sys.argv)>1 else 120; RP=78
s=socket.create_connection(('127.0.0.1',5555)); s.settimeout(0.5); buf=b''; sent=0; snaps=[]; rp=[]
t0=time.time()
while len(snaps)<N and time.time()-t0<120:
    try: buf+=s.recv(65536)
    except socket.timeout: pass
    if not sent and b'mono>' in buf: time.sleep(.3); s.sendall(b'demo smiley\r\n'); sent=time.time()
    while b'\n' in buf:
        l,buf=buf.split(b'\n',1); l=l.decode(errors='replace').replace('mono>','').strip()
        if not l.startswith('@F') or time.time()-sent<1.5: continue
        p=l.split(); rp.append([int(x) for x in p[5:9]]); snaps.append([t.split(':') for t in p[9:41]])
def lum(rows,idx):
    L=[];part=0
    for r in rows:
        b0,b1=int(r[0],16),int(r[3],16); o0,o1=int(r[idx]),int(r[idx+3])
        if (b0 and not o0) or (b1 and not o1): part+=1
        L+=[((o0 if b0>>x&1 else 0)+(o1 if b1>>x&1 else 0))/RP for x in range(32)]
    return L,part
res={'snapshots':len(snaps),'row_period_us_min':min(r[0] for r in rp),'row_period_us_max':max(r[1] for r in rp),
     'row_period_us_mean':round(st.mean(r[2] for r in rp)/10,2),'row_period_jitter_std_us':round(st.mean(max(r[3],0) for r in rp)**.5/10,2)}
for name,idx in (('nominal',1),('measured',2)):
    F=[];P=0
    for rows in snaps: L,p=lum(rows,idx); F.append(L); P+=p
    lit=[i for i in range(1024) if st.mean(f[i] for f in F)>0.02]
    std=[st.pstdev([f[i] for f in F]) for i in range(1024)]
    res[name]={'partial_rows':P,'led_std_mean':round(st.mean(std[i] for i in lit),4),'rel_std_pct':round(100*st.mean(std[i]/st.mean(f[i] for f in F) for i in lit),2)}
print(json.dumps(res))
