# R79 reel planner — R78 v3 rules (word-timed captions, speaker-follow faces, continuous tattoo shots w/ carried push)
import json, re, sys, math
sys.path.insert(0,'/root/r79reels'); from specs79 import SPECS, FIX
FPS=30000/1001; FR=1/FPS
W=json.load(open('/root/r79reels/words79.json')); RNG=json.load(open('/root/r79reels/ranges.json'))
PB=json.load(open('/root/r79/plan_base.json'))
OBSOFF=1.505                         # OBS time = mic time + 1.505
FACE={'P':('093A',[900,235]),'AC':('AVE',[1015,380])}
BOX=[(555,630.5,(401,101,1059,977)),(630.5,695.2,(140,72,1208,1000)),(695.2,745.3,(180,72,1020,1000)),
 (745.3,794.0,(285,72,1665,1000)),(794.0,834.3,(404,72,1104,984)),(834.3,846.9,(380,101,1081,977)),
 (846.9,905.0,(240,72,1260,1000)),(905.0,946.6,(390,72,1215,1000)),(946.6,961.0,(240,72,1665,1000)),
 (961.0,1008.4,(300,72,1710,1000)),(1008.4,1200,(360,72,1305,1000))]
def boxat(o):
    for a,b,bx in BOX:
        if a<=o<b: return list(bx)
LIVE=[]   # OBS-time live windows of the screen plan (no swipes/zooms inside)
for S in PB['SECT']:
    for p in S['pieces']:
        if p['kind']=='live': LIVE.append((p['o0'],p['o1']))
def fits(o,d):
    if not any(a<=o and o+d<=b for a,b in LIVE): return False
    return boxat(o)==boxat(o+d)
def fr(t): return int(round(t*FPS))
def norm(s): return re.sub(r"[^a-z0-9']","",s.lower())
out=[]
for S in SPECS:
    rid=S['id']
    # ---------- audio pieces ----------
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
    # ---------- words on the reel timeline ----------
    RW=[]
    for p in P:
        for k in range(p['i'],p['j']+1):
            w=W[k]; rt=p['f0']*FR+(w['t']-p['src0']); re_=p['f0']*FR+(min(w['end'],p['src0']+p['nf']*FR)-p['src0'])
            RW.append(dict(w=w['w'],s=w['s'],rt=max(rt,p['f0']*FR),re=re_,piece=P.index(p)))
    # speaker per frame + turns
    spk=['P']*NF
    for k,w in enumerate(RW):
        a=fr(w['rt']); b=fr(RW[k+1]['rt']) if k+1<len(RW) else NF
        for x in range(max(0,a),min(NF,b)): spk[x]=w['s']
    first=fr(RW[0]['rt'])
    for x in range(0,first): spk[x]=RW[0]['s']
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
        if hi>=NF-fr(0.5): return NF if NF-x<=fr(hi-x)/FPS*FPS else min(hi,NF)
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
    # fold tiny shots
    sh=[]
    for s in shots:
        if s['f1']-s['f0']<15 and sh: sh[-1]['f1']=s['f1']
        else: sh.append(s)
    shots=sh
    # ---------- materialize shots ----------
    def src_at(x):
        for p in P:
            if p['f0']<=x<p['f0']+p['nf']: return p['src0']+(x-p['f0'])*FR
        return P[-1]['src0']+P[-1]['nf']*FR
    def parts(a,b):
        out_=[]; x=a
        while x<b:
            p=next(p for p in P if p['f0']<=x<p['f0']+p['nf']); e=min(b,p['f0']+p['nf'])
            out_.append(dict(src=round(src_at(x),4),nf=e-x)); x=e
        return out_
    z=1.0; pool=S.get('pool'); pc=[0,pool[0][0]] if pool else None
    res=[]; lastbase={}; prevwho=None
    for k,s in enumerate(shots):
        xin=6 if k>0 and (s['kind']=='T' or shots[k-1]['kind']=='T') else 0
        if s['kind']=='F':
            cam,face=FACE[s['who']]
            base=1.0
            if prevwho==s['who']: base=1.18 if lastbase.get(s['who'],1.0)==1.0 else 1.0
            lastbase[s['who']]=base; prevwho=s['who']
            pp=parts(s['f0'],s['f1'])
            if xin: pp=[dict(src=round(pp[0]['src']-xin*FR,4),nf=xin)]+pp
            res.append(dict(f0=s['f0'],f1=s['f1'],kind='F',person=1 if s['who']=='P' else 2,base=base,xin=xin,cam=cam,face=face,parts=pp))
        else:
            prevwho=None
            nfr=s['f1']-s['f0']+xin; D=nfr*FR
            if pool:
                while True:
                    seg=pool[pc[0]]
                    if pc[1]+D<=seg[1] and boxat(pc[1])==boxat(pc[1]+D): break
                    if pc[1]+D>seg[1]: pc[0]=(pc[0]+1)%len(pool); pc[1]=pool[pc[0]][0]
                    else: pc[1]=next(b for a,b,_ in BOX if a<=pc[1]<b)+0.1
                o=pc[1]; pc[1]+=D; still=False
            else:
                o=src_at(s['f0'])+OBSOFF-xin*FR; still=False
                if not fits(o,D):
                    cand=sorted([o+d/10 for d in range(-150,151)],key=lambda t:abs(t-o))
                    ok=[t for t in cand if fits(t,D)]
                    if ok: o=ok[0]
                    else: still=True
            z0=z; z1=round(z0+0.018*D,4)
            if z1>1.16: z0=1.0; z1=round(1.0+0.018*D,4)
            z=z1
            res.append(dict(f0=s['f0'],f1=s['f1'],kind='T',xin=xin,obs=round(o-OBSOFF,3),still=still,box=boxat(o),z0=round(z0,4),z1=z1))
    out.append(dict(id=rid,slug=S['slug'],kind=S['kind'],handle=S['handle'],title=S['title'],
                    pieces=[dict(src0=p['src0'],nf=p['nf'],f0=p['f0']) for p in P],shots=res,frames=NF,dur=round(NF*FR,2),words=RW,turns=turns))
    nT=sum(1 for r in res if r['kind']=='T'); 
    print(rid,S['slug'],'dur %.1fs'%(NF*FR),'pieces',len(P),'shots',len(res),'T',nT,'cuts/min %.0f'%(len(res)/(NF*FR)*60),
          'turns',[(round(a*FR,1),s) for a,b,s in turns][:12])
json.dump(out,open('/root/r79reels/plan79.json','w'))
