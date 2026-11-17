import json, re, difflib, numpy as np, wave
words=json.load(open('words.json'))
norm=lambda s: re.sub(r"[^a-z0-9]","",s.lower())
T=[norm(w['w']) for w in words]
def anchors(asr):
    A=[norm(a[0]) for a in asr]; out={}
    for b in difflib.SequenceMatcher(None,T,A,autojunk=False).get_matching_blocks():
        for k in range(b.size): out[b.a+k]=(asr[b.b+k][1],asr[b.b+k][2],b.size)
    return out
al=anchors(json.load(open('au/asr_lm.json'))); ac=anchors(json.load(open('asr.json'))); ad=anchors(json.load(open('au/asr_dev.json')))
cand={}
for i,l in al.items():
    if l[2]>=2 or len(T[i])>=6: cand[i]=l[:2]
for i in set(ac)|set(ad):
    if i in cand: continue
    c,d=ac.get(i),ad.get(i)
    if c and d and abs(c[0]-d[0])<0.3: cand[i]=((c[0]+d[0])/2,(c[1]+d[1])/2)
    elif c and c[2]>=2: cand[i]=c[:2]
    elif d and d[2]>=2: cand[i]=d[:2]
# longest increasing subsequence on time
idx=sorted(cand); ts=[cand[i][0] for i in idx]
import bisect
tails=[];tidx=[];prev=[-1]*len(idx)
for j,t in enumerate(ts):
    k=bisect.bisect_left(tails,t)
    if k==len(tails): tails.append(t); tidx.append(j)
    else: tails[k]=t; tidx[k]=j
    prev[j]=tidx[k-1] if k else -1
seq=[];j=tidx[-1]
while j>=0: seq.append(j); j=prev[j]
keep=[idx[j] for j in reversed(seq)]
anc={i:cand[i] for i in keep}
# robust: drop anchors that disagree with a local linear fit of their neighbours
for it in range(6):
    ks=sorted(anc); K=np.array(ks,float); Tt=np.array([anc[k][0] for k in ks]); bad=[]
    for j in range(len(ks)):
        lo,hi=max(0,j-10),min(len(ks),j+11); m=[q for q in range(lo,hi) if q!=j]
        p=np.polyfit(K[m],Tt[m],1); r=Tt[j]-np.polyval(p,K[j])
        if abs(r)>max(3.0,abs(p[0])*15) or not (0.05<p[0]<1.5 and True): bad.append(ks[j]) if abs(r)>3.0 else None
    if not bad: break
    for b in bad: anc.pop(b)
    print('iter',it,'dropped',len(bad))
print('anchors',len(anc),'of',len(T))
# VAD on mix (10 ms)
w=wave.open('au/Left_Audio_Channel_54_16k.wav'); x=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(float)
e=20*np.log10(np.sqrt((x[:len(x)//160*160].reshape(-1,160)**2).mean(1))+1e-3)
thr=np.percentile(e,30)+8; voiced=(np.convolve(e>thr,np.ones(5),'same')>0)
cum=np.cumsum(voiced)
def vt(t): return cum[min(len(cum)-1,int(t*100))]
def inv(v):  # voiced-count -> time
    return np.searchsorted(cum,v)/100
keys=sorted(anc)
pts=[(-1,0.0)]+[(k,anc[k][0]) for k in keys]+[(len(T),len(x)/16000)]
for (i0,t0),(i1,t1) in zip(pts[:-1],pts[1:]):
    a=i0 if i0>=0 else 0
    if i0>=0: words[i0]['s'],words[i0]['e']=anc[i0]
    inner=list(range(i0+1,i1))
    if not inner: continue
    st=anc[i0][1] if i0>=0 else t0
    wts=np.array([max(2,len(T[i])) for i in inner],float); 
    v0,v1=vt(st),vt(t1)
    if v1-v0<len(inner)*5:  # too little voicing -> linear
        edges=np.linspace(st,t1,len(inner)+1)
    else:
        cw=np.r_[0,np.cumsum(wts)]/wts.sum(); edges=[inv(v0+(v1-v0)*c) for c in cw]
    for n,i in enumerate(inner): words[i]['s']=round(float(edges[n]),2); words[i]['e']=round(float(max(edges[n+1],edges[n]+0.05)),2)
for i,wd in enumerate(words): wd['anc']=i in anc
json.dump(words,open('words_t.json','w'))
# print a readable timed transcript with ~every sentence
out=[];line=[]
for wd in words:
    line.append(wd['w']+wd['p'])
    if wd['p'] and wd['p'][-1] in '.?!' and len(line)>6:
        out.append(f"{int(st_//60):02d}:{st_%60:05.2f}  "+' '.join(line)); line=[]
    if len(line)==1: st_=wd['s']
open('timed.txt','w').write('\n'.join(out)); print(len(out),'lines')
