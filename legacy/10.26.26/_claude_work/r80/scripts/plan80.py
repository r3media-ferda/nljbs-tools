import numpy as np, json
FPS=30000/1001
OFF={'AVE':-40.9585,'093A':-61.856,'C':-81.128,'OBS':-64.4875}   # video start in mic time
B0,B1=100.80,1594.30
OUT0=1441.60                     # outro ("let's start with Jacob") -> cameras only
# ---------- mic levels: 50 ms steps from 10 ms band levels ----------
L10=np.load('lev80.npy'); n=L10.shape[1]//5
P=10**(L10[:,:n*5]/10); L=10*np.log10(P.reshape(3,n,5).mean(2)+1e-12)   # frame i = (i*0.05+0.025..)
np.save('mic_levels.npy',L)
act=L.max(0)>np.percentile(L.max(0),35)
o=np.argsort(-L,axis=0); top=o[0]; lead=np.take_along_axis(L,o[:1],0)[0]-np.take_along_axis(L,o[1:2],0)[0]
lab=np.where(act&(lead>4),top+1,0)          # 1 Porter, 2 AC, 3 Jake
N=n//2; l10=lab[:N*2].reshape(N,2)
silent=(lab[:N*2].reshape(N,2)==0).all(1)&(~act[:N*2].reshape(N,2)).all(1)
k0,k1=int(B0*10),int(B1*10)
sm=np.zeros(N,int)
for i in range(k0,k1):
    ww=l10[max(0,i-6):i+7].ravel(); ww=ww[ww>0]
    sm[i]=0 if len(ww)==0 else np.bincount(ww,minlength=4).argmax()
cur=1; seq=[]
for i in range(k0,k1):
    s=sm[i] if sm[i]>0 else cur; cur=s; seq.append(s)
runs=[]
for j,s in enumerate(seq):
    t=B0+j*0.1
    if runs and runs[-1][2]==s: runs[-1][1]=t+0.1
    else: runs.append([t,t+0.1,int(s)])
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
print('speaker runs',len(runs),{k:round(sum(r[1]-r[0] for r in runs if r[2]==k)) for k in (1,2,3)})
# ---------- screen ----------
dd=np.load('diff10.npy'); T0=0
auto={r['k']:r for r in json.load(open('boxes_auto2.json'))}
FIX={46:'G2a',47:'G2a',48:'G2a',49:'G2a',50:'G2a',51:'G2a',52:'G2a',53:'G2a',54:'G2a',55:'G2a',
     **{k:'G2c' for k in range(59,72)},80:'G2f',86:[463,102,997,1054],96:[348,96,1170,1055],
     128:[380,96,1231,1077],129:[340,99,1108,1077],130:[340,99,1108,1077],44:[57,99,944,1077],45:[57,99,944,1077]}
GB={'G2a':[463,102,997,1054],'G2c':[488,99,1158,1077],'G2f':[432,95,1045,1077]}
HOLDK={35,72,73,85,115}          # profile pages / grids -> hold the last good post
BOX=[]
for k in sorted(auto):
    r=auto[k]; b=FIX.get(k,r['box']); b=GB[b] if isinstance(b,str) else b
    BOX.append((r['a'],b,k in HOLDK))
def boxat(o):
    cur=None
    for a,b,h in BOX:
        if a<=o+0.05: cur=(b,h)
        else: break
    return cur
VIDEO=[(243,410),(420,440),(561,640),(667,770),(786,840),(850,980),(1338,1358),(1388,1410)]
def invid(o): return any(a<=o<b for a,b in VIDEO)
SECT=[dict(id='S1',o0=243.6,o1=561.0,handle='matty_d_mooney',PA=0.80),
      dict(id='S2',o0=561.0,o1=982.0,handle='jeremiahbarba',PA=0.70),
      dict(id='S3',o0=982.0,o1=OUT0-OFF['OBS'],handle='cololopeztattoo',PA=0.85)]
holds=[]
for S in SECT:
    a,b=int(S['o0']*10),int(S['o1']*10)
    seg=dd[a:b]; ot=np.arange(a,b)/10
    tr=np.array([v>=(16 if invid(t) else 9) for v,t in zip(seg,ot)])
    hb=np.array([boxat(t)[1] for t in ot])
    tr|=hb
    for x0,_,_ in BOX:
        i=int(x0*10)-a
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
    if m[0][2] and len(m)>1: m[1][0]=0; m.pop(0)       # section can't open on a hold
    S['pieces']=[]
    for i,j,t in m:
        o0=(a+i)/10; o1=(a+j)/10
        if not t: S['pieces'].append(dict(o0=o0,o1=o1,kind='live',box=boxat((o0+o1)/2)[0],video=invid((o0+o1)/2)))
        else: S['pieces'].append(dict(o0=o0,o1=o1,kind='hold'))
    Pc=S['pieces']
    for i,p in enumerate(Pc):
        if p['kind']!='hold': continue
        prev=next((Pc[k] for k in range(i-1,-1,-1) if Pc[k]['kind']=='live'),None)
        nxt=next((Pc[k] for k in range(i+1,len(Pc)) if Pc[k]['kind']=='live'),None)
        src=prev or nxt
        p['box']=src['box']; p['still_t']=round(src['o1']-0.15 if prev else src['o0']+0.2,2)
        p['still']="hold_%s_%07.2f.jpg"%(S['id'],p['still_t']); holds.append(dict(t=p['still_t'],f=p['still']))
    for p in Pc: p['m0']=round(p['o0']+OFF['OBS'],3); p['m1']=round(p['o1']+OFF['OBS'],3)
    S['m0']=Pc[0]['m0']; S['m1']=Pc[-1]['m1']
    print(S['id'],S['handle'],'mic %.1f-%.1f'%(S['m0'],S['m1']),'pieces',len(Pc),'live',round(sum(p['o1']-p['o0'] for p in Pc if p['kind']=='live'),1),'hold',round(sum(p['o1']-p['o0'] for p in Pc if p['kind']=='hold'),1))
# ---------- dead air ----------
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
print('holds',len(holds))
json.dump(dict(B0=B0,B1=B1,OUT0=OUT0,OFF=OFF,runs=runs,SECT=SECT,holds=holds,cuts=cuts,video_sil=vsil),open('plan_base.json','w'),default=float)
