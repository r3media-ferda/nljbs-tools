import numpy as np, json
SR=16000; W=800; H=160
def band(x):
    n=(len(x)-W)//H; out=np.zeros(n,np.float32); win=np.hanning(W).astype(np.float32)
    f=np.fft.rfftfreq(W,1/SR); m=(f>=150)&(f<=3500)
    for s in range(0,n,20000):
        idx=np.arange(s,min(n,s+20000))[:,None]*H+np.arange(W)
        F=np.abs(np.fft.rfft(x[idx]*win,axis=1))[:,m]**2
        out[s:s+len(F)]=10*np.log10(F.mean(1)+1e-12)
    return out
L=np.stack([band(np.fromfile(f'm{i}.f32',np.float32)) for i in (1,2,3)])  # frames at 10 ms, centered +25 ms
np.save('lev80.npy',L)
w=json.load(open('words80.json'))['words']
ons=[t for _,t in w]
spk=[];prev=0;D=[]
for i,(x,t) in enumerate(w):
    a=t+0.02; b=min(ons[i+1] if i+1<len(w) else t+0.45, t+0.45); b=max(b,a+0.06)
    fa,fb=int((a-0.025)*100),int((b-0.025)*100)+1
    seg=L[:,max(0,fa):fb]; lv=np.log10(np.mean(10**(seg/10),axis=1))*10
    o=np.argsort(lv)[::-1]; lead=lv[o[0]]-lv[o[1]]; D.append(lv.tolist())
    s=int(o[0]) if lead>5 else prev
    spk.append(s); prev=s
# fold 1-word islands
for i in range(1,len(spk)-1):
    if spk[i-1]==spk[i+1]!=spk[i]: spk[i]=spk[i-1]
names=['PORTER','AC','JAKE']
json.dump([[x,t,names[s]] for (x,t),s in zip(w,spk)],open('words80_spk.json','w'))
from collections import Counter; print(Counter(names[s] for s in spk))
# transcript by turn
out=[];cur=None
for (x,t),s in zip(w,spk):
    if cur is None or s!=cur[1] or len(cur[2])>40:
        if cur: out.append('%7.1f %-6s %s'%(cur[0],names[cur[1]],' '.join(cur[2])))
        cur=[t,s,[]]
    cur[2].append(x)
out.append('%7.1f %-6s %s'%(cur[0],names[cur[1]],' '.join(cur[2])))
open('transcript80_spk.txt','w').write('\n'.join(out)); print(len(out))
