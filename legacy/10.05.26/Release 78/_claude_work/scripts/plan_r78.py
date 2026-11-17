import numpy as np, json
FPS=30000/1001
OFF={'AVE':-10.17,'093A':-36.675,'C':4.008,'OBS':17.701}
OBSLEN=1302.68; MICLEN=1308.0
# ---------------- speaker labels (50ms) ----------------
L=np.load('mic_levels.npy'); n=L.shape[1]
A=L-np.array([0,0,1.5])[:,None]
top=np.argmax(A,0); mx=A.max(0); sec=np.sort(A,0)[-2]
lab=np.where(mx<-47,0,np.where(mx-sec>4,top+1,np.where(sec>-44,4,top+1)))
# 0.1s grid
N=n//2; lab10=lab[:N*2].reshape(N,2)
def mode10(r):
    r=r[r>0]; return 0 if len(r)==0 else np.bincount(r,minlength=5).argmax()
l10=np.array([mode10(r) for r in lab10])
silent=(lab10==0).all(1)
# ---------------- body range ----------------
def silruns(minlen):
    out=[];i=0
    while i<N:
        if silent[i]:
            j=i
            while j<N and silent[j]: j+=1
            if (j-i)/10>=minlen: out.append((i/10,j/10))
            i=j
        else: i+=1
    return out
S03=silruns(0.3)
B0=next(b for a,b in S03 if a>=12.0)-0.15
B1=[a for a,b in S03 if b<=1307.6 and a<1306.5][-1]+0.25
print('body',B0,B1,round(B1-B0,1))
# ---------------- speaker runs ----------------
k0,k1=int(B0*10),int(B1*10)
sm=np.zeros(N,int)
for i in range(k0,k1):
    w=l10[max(0,i-6):i+7]; w=w[w>0]
    sm[i]=0 if len(w)==0 else np.bincount(w,minlength=5).argmax()
cur=1; seq=[]
for i in range(k0,k1):
    s=sm[i] if sm[i]>0 else cur; cur=s; seq.append(s)
runs=[]
for j,s in enumerate(seq):
    t=B0+j*0.1
    if runs and runs[-1][2]==s: runs[-1][1]=t+0.1
    else: runs.append([t,t+0.1,s])
def merge(runs,minlen,minlen_overlap):
    ch=True
    while ch:
        ch=False
        for i,r in enumerate(runs):
            lim=minlen_overlap if r[2]==4 else minlen
            if r[1]-r[0]<lim and len(runs)>1:
                # absorb into the longer neighbour
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
runs=merge(runs,2.6,3.0)
runs[0][0]=B0; runs[-1][1]=B1
from collections import Counter
print('speaker runs',len(runs),{k:round(sum(r[1]-r[0] for r in runs if r[2]==k)) for k in (1,2,3,4)})
# ---------------- screen pieces ----------------
g=np.fromfile('obs_10fps_g.raw',np.uint8).reshape(-1,72,128).astype(np.int16)
d=np.r_[0,np.abs(np.diff(g,axis=0)).mean((1,2))]
Bx=np.load('B.npy')
SECT=[dict(id='S1',o0=282.7,o1=511.3,handle='chadchesko',PA=0.744,crop=(684,75,1432,1080)),
      dict(id='S2',o0=512.4,o1=770.8,handle='tiger_ramos',PA=0.964,crop=(292,96,1168,1005)),
      dict(id='S3',o0=772.3,o1=OBSLEN-0.1,handle='stewart_modernclassic',PA=0.62,crop=None)]
holds=[]; pieces=[]
def dil(m,r):
    o=m.copy()
    for s in range(1,r+1): o[s:]|=m[:-s]; o[:-s]|=m[s:]
    return o
for S in SECT:
    a,b=int(S['o0']*10),int(S['o1']*10)
    dd=d[a:b]
    if S['id']=='S2':
        tr=dil(dd>=14,1)
        # tattoo videos inside the carousel: a sustained run of motion (>=3 s) plays live, even through its own jump cuts
        act=dd>0.3; i=0
        while i<len(act):
            if act[i]:
                j=i; gap=0
                while j<len(act) and (act[j] or gap<5):
                    gap=0 if act[j] else gap+1; j+=1
                j-=gap
                if j-i>=30 and (dd[i:j]>0.3).mean()>0.6: tr[i+5:j-5]=False
                i=j
            else: i+=1
    else: tr=dil(dd>0.3,1)
    tr[:2]=False
    # runs
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
    for idx,(i,j,t) in enumerate(m):
        o0=(a+i)/10; o1=(a+j)/10
        if not t:
            if S['crop']: box=S['crop']
            else:
                bs=Bx[int(o0*2)+1:int(o1*2)]; bs=bs[bs[:,0]>=0]
                x0,x1,y0,y1=np.median(bs,0).astype(int).tolist(); box=(x0,y0,x1,min(y1,1045))
            vid=bool(S['id']=='S2' and (dd[i:j]>0.3).mean()>0.4)
            S['pieces'].append(dict(o0=o0,o1=o1,kind='live',box=box,video=vid))
        else:
            S['pieces'].append(dict(o0=o0,o1=o1,kind='hold'))
    # assign hold frames
    P=S['pieces']
    for i,p in enumerate(P):
        if p['kind']!='hold': continue
        prev=next((P[k] for k in range(i-1,-1,-1) if P[k]['kind']=='live'),None)
        nxt=next((P[k] for k in range(i+1,len(P)) if P[k]['kind']=='live'),None)
        src=prev or nxt
        p['box']=src['box']; p['still_t']=round(src['o1']-0.2 if prev else src['o0']+0.2,2)
        p['still']=f"hold_{S['id']}_{len(holds)+1:03d}.png"; holds.append(dict(t=p['still_t'],f=p['still']))
    for p in P: p['m0']=round(p['o0']+OFF['OBS'],3); p['m1']=round(p['o1']+OFF['OBS'],3)
    S['m0']=S['pieces'][0]['m0']; S['m1']=S['pieces'][-1]['m1']
    print(S['id'],'pieces',len(P),'live',round(sum(p['o1']-p['o0'] for p in P if p['kind']=='live'),1),'hold',round(sum(p['o1']-p['o0'] for p in P if p['kind']=='hold'),1),'video',round(sum(p['o1']-p['o0'] for p in P if p.get('video')),1))
    for p in P:
        if S['id']!='S2' or p['kind']=='hold' and p['o1']-p['o0']>1: print('   ',p['kind'],p['o0'],p['o1'],p.get('box'),p.get('video',''))
# extend S3 to the end of the body
SECT[-1]['m1']=max(SECT[-1]['m1'],B1)
# ---------------- silence tightening (dead air) ----------------
def in_video(t):
    for S in SECT:
        for p in S['pieces']:
            if p.get('video') and p['m0']<=t<p['m1']: return True
    return False
cuts=[]; keep_video_sil=[]
for a,b in silruns(2.0):
    if a<B0+1 or b>B1-1: continue
    mid=(a+b)/2
    if in_video(a+0.5) or in_video(mid): keep_video_sil.append((a,b)); continue
    c0,c1=a+0.45,b-0.45
    if c1-c0>0.5: cuts.append((round(c0,2),round(c1,2)))
print('cuts',len(cuts),'removed',round(sum(b-a for a,b in cuts),1),'s', cuts)
print('silences kept for tattoo video',keep_video_sil)
json.dump(dict(B0=B0,B1=B1,OFF=OFF,runs=runs,SECT=SECT,holds=holds,cuts=cuts,video_sil=keep_video_sil),open('plan_base.json','w'),default=float)
