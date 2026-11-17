# R80 reel planner — R78 v3 / R79 rules, 3 speakers (Porter 093A, AC + Jake share AVE -> per-shot YuNet face pick)
import json, re, sys, os, subprocess
H='/tmp/reels80'; sys.path.insert(0,H); from specs80 import SPECS, FIX
import cv2, numpy as np
FPS=30000/1001; FR=1/FPS
RAW=json.load(open('/tmp/r80/words80_spk.json'))
SP={'PORTER':'P','AC':'AC','JAKE':'J'}
W=[]
for k,(w,t,s) in enumerate(RAW):
    nt=RAW[k+1][1] if k+1<len(RAW) else t+0.6
    W.append(dict(w=w,t=t,end=round(min(nt-0.02,t+0.10+0.07*len(w)),3),s=SP[s]))
def norm(s): return re.sub(r"[^a-z0-9']","",s.lower())
# ---------- resolve ranges -> word indices ----------
RNG={}
for S in SPECS:
    rr=[]
    for t0,fw,t1,lw,_ in S['ranges']:
        ci=[k for k,w in enumerate(W) if abs(w['t']-t0)<2.5 and norm(w['w']).startswith(norm(fw))]
        cj=[k for k,w in enumerate(W) if abs(w['t']-t1)<2.5 and norm(w['w']).startswith(norm(lw))]
        if not ci or not cj: sys.exit(f"resolve fail {S['id']} {fw}@{t0} / {lw}@{t1}")
        i=min(ci,key=lambda k:abs(W[k]['t']-t0)); j=min(cj,key=lambda k:abs(W[k]['t']-t1))
        assert j>=i,(S['id'],fw,lw); rr.append((i,j))
    RNG[S['id']]=rr
PB=json.load(open('/tmp/r80/plan_base.json'))
OBSOFF=64.4875                       # OBS time = mic time + 64.4875
CAMOFF={'AVE':40.9585,'093A':61.856}
SRC={'AVE':os.path.expanduser('~/mnt/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 2/AVE14202.MP4'),
     '093A':os.path.expanduser('~/mnt/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 2/093A6724.MP4')}
CAM={'P':'093A','AC':'AVE','J':'AVE'}
DEF={'P':[1130,370],'AC':[580,345],'J':[1515,470]}
PIECES=[p for S in PB['SECT'] for p in S['pieces']]
LIVE=[(p['o0'],p['o1']) for p in PIECES if p['kind']=='live']
def boxat(o):
    for p in PIECES:
        if p['o0']<=o<p['o1']: return list(p['box'])
    return None
def fits(o,d):
    if not any(a<=o and o+d<=b for a,b in LIVE): return False
    return boxat(o)==boxat(o+d)
det=cv2.FaceDetectorYN.create(H+'/yunet.onnx','',(1920,1080),0.6)
def face_for(who,mic_t):
    cam=CAM[who]; t=mic_t+CAMOFF[cam]
    raw=subprocess.run(['ffmpeg','-v','error','-ss',f'{t:.3f}','-i',SRC[cam],'-frames:v','1','-f','rawvideo','-pix_fmt','bgr24','-'],capture_output=True).stdout
    if len(raw)<1920*1080*3: return DEF[who]
    im=np.frombuffer(raw,np.uint8).reshape(1080,1920,3); _,fs=det.detect(im)
    if fs is None: return DEF[who]
    c=[(x+w/2,y+h/2,w) for x,y,w,h,*r in fs if w>70]
    if who=='P': c=[f for f in c if f[0]>600]
    elif who=='AC': c=[f for f in c if f[0]<1000]
    else: c=[f for f in c if f[0]>1000]
    if not c: return DEF[who]
    f=max(c,key=lambda f:f[2]); return [int(f[0]),int(f[1])]
def fr(t): return int(round(t*FPS))
out=[]
for S in SPECS:
    rid=S['id']
    pieces=[]
    for (i,j) in RNG[rid]:
        st=max(W[i]['t']-0.08,(W[i-1]['end']+0.02) if i>0 else 0)
        segs=[]; cur=st
        for k in range(i,j):
            gap=W[k+1]['t']-W[k]['end']
            if gap>0.30:
                e=min(max(W[k]['end']+0.08,W[k]['t']+0.35),W[k+1]['t']-0.08); s2=W[k+1]['t']-0.08
                if s2-e>0.15: segs.append((cur,e,i,k)); cur=s2; i=k+1
        e=min(W[j]['end']+0.08,(W[j+1]['t']-0.03) if j+1<len(W) else W[j]['end']+0.08)
        segs.append((cur,e,i,j))
        pieces+=segs
    P=[]; f=0
    for a,b,i,j in pieces:
        nf=fr(b-a); P.append(dict(src0=round(a,4),nf=nf,f0=f,i=i,j=j)); f+=nf
    NF=f
    RW=[]
    for pi,p in enumerate(P):
        for k in range(p['i'],p['j']+1):
            w=W[k]; rt=p['f0']*FR+(w['t']-p['src0']); re_=p['f0']*FR+(min(w['end'],p['src0']+p['nf']*FR)-p['src0'])
            RW.append(dict(w=w['w'],s=w['s'],rt=max(rt,p['f0']*FR),re=re_,piece=pi))
    spk=['P']*NF
    for k,w in enumerate(RW):
        a=fr(w['rt']); b=fr(RW[k+1]['rt']) if k+1<len(RW) else NF
        for x in range(max(0,a),min(NF,b)): spk[x]=w['s']
    for x in range(0,fr(RW[0]['rt'])): spk[x]=RW[0]['s']
    turns=[]
    for x,s in enumerate(spk):
        if turns and turns[-1][2]==s: turns[-1][1]=x+1
        else: turns.append([x,x+1,s])
    ch=True
    while ch:
        ch=False
        for k,t in enumerate(turns):
            if t[1]-t[0]<18 and len(turns)>1:
                if k>0: turns[k-1][1]=t[1]
                else: turns[1][0]=t[0]
                turns.pop(k); ch=True; break
        m=[]
        for t in turns:
            if m and m[-1][2]==t[2]: m[-1][1]=t[1]
            else: m.append(t)
        turns=m
    def spk_at(x):
        for a,b,s in turns:
            if a<=x<b: return s
        return turns[-1][2]
    def next_change(x):
        for a,b,s in turns:
            if a<=x<b: return b
        return NF
    PBOUND=set(p['f0'] for p in P[1:]); ONS=sorted(set(fr(w['rt']) for w in RW))
    def pick(x,lo,hi,target):
        lo=x+fr(lo); hi=min(NF,x+fr(hi)); tg=x+fr(target)
        if hi>=NF-fr(0.5): return min(hi,NF) if NF-x>fr(hi-x) else NF
        c=[b for b in PBOUND if lo<=b<=hi]
        if c: return min(c,key=lambda b:abs(b-tg))
        c=[o for o in ONS if lo<=o<=hi]
        if c: return min(c,key=lambda o:abs(o-tg))
        return min(hi,max(lo,tg))
    shots=[]; x=0
    if S['kind']=='talk':
        e=pick(x,0.7,1.3,1.0); e=min(e,next_change(x)) if next_change(x)>fr(0.5) else e
        shots.append(dict(f0=0,f1=e,kind='F',who=spk_at(0))); x=e
        while x<NF:
            nc=next_change(x); rem=nc-x
            e=nc if rem<=fr(3.6) else pick(x,2.4,3.6,3.0)
            shots.append(dict(f0=x,f1=e,kind='F',who=spk_at(x))); x=e
    else:
        e=pick(x,0.7,1.3,1.0); shots.append(dict(f0=0,f1=e,kind='F',who=spk_at(0))); x=e; nxt='T'
        while x<NF:
            if nxt=='T':
                e=pick(x,2.2,3.6,3.0); shots.append(dict(f0=x,f1=e,kind='T')); nxt='F'
            else:
                nc=next_change(x)
                e=nc if fr(1.0)<=nc-x<=fr(2.6) else pick(x,1.6,2.6,2.2)
                if nc-x<fr(1.0) and nc<NF: e=max(nc,x+fr(0.6))
                shots.append(dict(f0=x,f1=e,kind='F',who=spk_at(x))); nxt='T'
            x=e
    sh=[]
    for s in shots:
        if s['f1']-s['f0']<15 and sh: sh[-1]['f1']=s['f1']
        else: sh.append(s)
    shots=sh
    def src_at(x):
        for p in P:
            if p['f0']<=x<p['f0']+p['nf']: return p['src0']+(x-p['f0'])*FR
        return P[-1]['src0']+P[-1]['nf']*FR
    def parts(a,b):
        o=[]; x=a
        while x<b:
            p=next(p for p in P if p['f0']<=x<p['f0']+p['nf']); e=min(b,p['f0']+p['nf'])
            o.append(dict(src=round(src_at(x),4),nf=e-x)); x=e
        return o
    z=1.0; pool=S.get('pool'); pc=[0,pool[0][0]] if pool else None
    res=[]; lastbase={}; prevwho=None; prev_obs_end=None
    for k,s in enumerate(shots):
        xin=6 if k>0 and (s['kind']=='T' or shots[k-1]['kind']=='T') else 0
        if s['kind']=='F':
            cam=CAM[s['who']]
            base=1.0
            if prevwho==s['who']: base=1.18 if lastbase.get(s['who'],1.0)==1.0 else 1.0
            lastbase[s['who']]=base; prevwho=s['who']
            pp=parts(s['f0'],s['f1'])
            if xin: pp=[dict(src=round(pp[0]['src']-xin*FR,4),nf=xin)]+pp
            mid=pp[len(pp)//2]['src']+pp[len(pp)//2]['nf']*FR/2
            res.append(dict(f0=s['f0'],f1=s['f1'],kind='F',who=s['who'],base=base,xin=xin,cam=cam,face=face_for(s['who'],mid),parts=pp))
        else:
            prevwho=None
            nfr=s['f1']-s['f0']+xin; D=nfr*FR
            o=src_at(s['f0'])+OBSOFF-xin*FR; still=False
            CL=S.get('clamp',(0,1e9))
            if not fits(o,D) or not (CL[0]<=o and o+D<=CL[1]):
                cand=sorted([o+d/10 for d in range(-1500,1501)],key=lambda t:abs(t-o))
                ok=[t for t in cand if CL[0]<=t and t+D<=CL[1] and fits(t,D)]
                if ok: o=ok[0]
                else: still=True
            # carried push resets when the tattoo (box) changes
            if res and any(r['kind']=='T' for r in res):
                lastT=[r for r in res if r['kind']=='T'][-1]
                if lastT['box']!=boxat(o): z=1.0
            z0=z; z1=round(z0+0.018*D,4)
            if z1>1.16: z0=1.0; z1=round(1.0+0.018*D,4)
            z=z1
            bx=boxat(o) or next((r['box'] for r in res[::-1] if r['kind']=='T'),None) or [463,102,997,1054]
            x0,y0,x1,y1=bx
            if (x1-x0)/(y1-y0)>1.15:
                cx=(x0+x1)/2; w=(y1-y0)*0.95; bx=[int(cx-w/2),y0,int(cx+w/2),y1]
            res.append(dict(f0=s['f0'],f1=s['f1'],kind='T',xin=xin,obs=round(o-OBSOFF,3),still=still,box=bx,z0=round(z0,4),z1=z1))
    out.append(dict(id=rid,slug=S['slug'],kind=S['kind'],handle=S['handle'],title=S['title'],
                    pieces=[dict(src0=p['src0'],nf=p['nf'],f0=p['f0']) for p in P],shots=res,frames=NF,dur=round(NF*FR,2),words=RW,turns=turns))
    nT=sum(1 for r in res if r['kind']=='T'); nS=sum(1 for r in res if r.get('still'))
    print(rid,S['slug'],'dur %.1fs'%(NF*FR),'pieces',len(P),'shots',len(res),'T',nT,'stills',nS,'cuts/min %.0f'%(len(res)/(NF*FR)*60),
          'who',''.join(r.get('who','T')[0] for r in res))
json.dump(out,open(H+'/plan80r.json','w'))
