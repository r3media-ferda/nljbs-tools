import numpy as np, json
FPS=30000/1001
OFF={'AVE':8.233,'093A':4.234,'C':15.522,'OBS':-1.505}   # video start in mic time
END093=4.234+1480.312-0.1                                  # 093A runs out here (mic time)
B0,B1=260.55,1482.15
OUT0=1385.55                                               # outro: "how can people find you" -> cameras only
# ---------------- speaker runs (1=P mic1 -> 093A, 2=AC mic2 -> AVE) ----------------
L=np.load('mic_levels.npy'); n=L.shape[1]
d=L[1]-L[0]; act=L.max(0)>-47
lab=np.where(~act,0,np.where(d>-4,2,np.where(d<-8,1,0)))
N=n//2; l10=lab[:N*2].reshape(N,2)
def m10(r):
    r=r[r>0]; return 0 if len(r)==0 else np.bincount(r,minlength=3).argmax()
l10=np.array([m10(r) for r in l10])
silent=(lab[:N*2].reshape(N,2)==0).all(1) & (L.max(0)[:N*2].reshape(N,2).max(1)<-47)
k0,k1=int(B0*10),int(B1*10)
sm=np.zeros(N,int)
for i in range(k0,k1):
    w=l10[max(0,i-6):i+7]; w=w[w>0]
    sm[i]=0 if len(w)==0 else np.bincount(w,minlength=3).argmax()
cur=1; seq=[]
for i in range(k0,k1):
    s=sm[i] if sm[i]>0 else cur; cur=s; seq.append(s)
runs=[]
for j,s in enumerate(seq):
    t=B0+j*0.1
    if runs and runs[-1][2]==s: runs[-1][1]=t+0.1
    else: runs.append([t,t+0.1,s])
def merge(runs,minlen):
    ch=True
    while ch:
        ch=False
        for i,r in enumerate(runs):
            if r[1]-r[0]<minlen and len(runs)>1:
                if i==0: runs[1][0]=r[0]
                elif i==len(runs)-1: runs[i-1][1]=r[1]
                elif runs[i-1][1]-runs[i-1][0]>=runs[i+1][1]-runs[i+1][0]: runs[i-1][1]=r[1]
                else: runs[i+1][0]=r[0]
                runs.pop(i); ch=True; break
        m=[]
        for r in runs:
            if m and m[-1][2]==r[2]: m[-1][1]=r[1]
            else: m.append(r)
        runs=m
    return runs
runs=merge(runs,2.6); runs[0][0]=B0; runs[-1][1]=B1
print('speaker runs',len(runs),{k:round(sum(r[1]-r[0] for r in runs if r[2]==k)) for k in (1,2)})
# ---------------- screen ----------------
dd=np.load('diff10.npy'); T0=555
BOX=[  # OBS time ranges -> image box (x0,y0,x1,y1) measured from frames
 (555,630.5,(401,101,1059,977)),(630.5,695.2,(140,72,1208,1000)),(695.2,745.3,(180,72,1020,1000)),
 (745.3,770.0,(285,72,1665,1000)),(770.0,794.0,(285,72,1665,1000)),(794.0,834.3,(404,72,1104,984)),
 (834.3,846.9,(380,101,1081,977)),(846.9,905.0,(240,72,1260,1000)),(905.0,946.6,(390,72,1215,1000)),
 (946.6,961.0,(240,72,1665,1000)),(961.0,991.0,(300,72,1710,1000)),(991.0,1008.4,(300,72,1710,1000)),
 (1008.4,1200,(360,72,1305,1000))]
def boxat(o):
    for a,b,bx in BOX:
        if a<=o<b: return bx
VIDEO=[(567.5,627.0),(697.5,727.5),(794.5,834.0)]   # moth reel playing
def invid(o): return any(a<=o<b for a,b in VIDEO)
SECT=[dict(id='S1',o0=568.0,o1=834.3,handle='cum_eels',PA=0.75),
      dict(id='S2',o0=834.3,o1=1102.5,handle='smithtattoosf',PA=0.90)]
holds=[]
for S in SECT:
    a,b=int((S['o0']-T0)*10),int((S['o1']-T0)*10)
    seg=dd[a:b]; o=np.arange(a,b)/10+T0
    tr=np.array([v>=(14 if invid(t) else 9) for v,t in zip(seg,o)])
    # also force holds at box-state boundaries
    for x0,x1,_ in BOX:
        for e in (x0,):
            i=int((e-T0)*10)-a
            if 0<i<len(tr): tr[max(0,i-2):i+3]=True
    t2=tr.copy()
    for s in range(1,4): t2[s:]|=tr[:-s]; t2[:-s]|=tr[s:]
    tr=t2; tr[:3]=False
    rr=[];i=0
    while i<len(tr):
        j=i
        while j<len(tr) and tr[j]==tr[i]: j+=1
        rr.append([i,j,bool(tr[i])]); i=j
    for r in rr:
        if not r[2] and (r[1]-r[0])<7: r[2]=True
    m=[]
    for r in rr:
        if m and m[-1][2]==r[2]: m[-1][1]=r[1]
        else: m.append(r)
    S['pieces']=[]
    for i,j,t in m:
        o0=(a+i)/10+T0; o1=(a+j)/10+T0
        if not t: S['pieces'].append(dict(o0=o0,o1=o1,kind='live',box=boxat((o0+o1)/2),video=invid((o0+o1)/2)))
        else: S['pieces'].append(dict(o0=o0,o1=o1,kind='hold'))
    P=S['pieces']
    for i,p in enumerate(P):
        if p['kind']!='hold': continue
        prev=next((P[k] for k in range(i-1,-1,-1) if P[k]['kind']=='live'),None)
        nxt=next((P[k] for k in range(i+1,len(P)) if P[k]['kind']=='live'),None)
        src=prev or nxt
        p['box']=src['box']; p['still_t']=round(src['o1']-0.15 if prev else src['o0']+0.2,2)
        p["still"]=f"hold_{S['id']}_{p['still_t']:07.2f}.png"; holds.append(dict(t=p['still_t'],f=p['still']))
    for p in P: p['m0']=round(p['o0']+OFF['OBS'],3); p['m1']=round(p['o1']+OFF['OBS'],3)
    S['m0']=P[0]['m0']; S['m1']=P[-1]['m1']
    print(S['id'],'pieces',len(P),'live',round(sum(p['o1']-p['o0'] for p in P if p['kind']=='live'),1),'hold',round(sum(p['o1']-p['o0'] for p in P if p['kind']=='hold'),1))
# ---------------- dead air ----------------
def silruns(minlen):
    out=[];i=int(B0*10)
    while i<int(B1*10):
        if silent[i]:
            j=i
            while j<N and silent[j]: j+=1
            if (j-i)/10>=minlen: out.append((i/10,j/10))
            i=j
        else: i+=1
    return out
def in_video(t):
    for S in SECT:
        for p in S['pieces']:
            if p.get('video') and p['m0']<=t<p['m1']: return True
    return False
cuts=[]; vsil=[]
for a,b in silruns(2.0):
    if a<B0+1 or b>B1-1: continue
    if in_video(a+0.5) or in_video((a+b)/2): vsil.append((a,b)); continue
    c0,c1=a+0.45,b-0.45
    if c1-c0>0.5: cuts.append((round(c0,2),round(c1,2)))
print('cuts',len(cuts),'removed',round(sum(b-a for a,b in cuts),1),cuts)
print('video silences',vsil)
json.dump(dict(B0=B0,B1=B1,OUT0=OUT0,END093=END093,OFF=OFF,runs=runs,SECT=SECT,holds=holds,cuts=cuts,video_sil=vsil),open('plan_base.json','w'),default=float)
