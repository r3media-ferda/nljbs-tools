import numpy as np, os, json
D=os.path.expanduser('~/r77'); SR=8000
def load(n): return np.fromfile(f'{D}/{n}.raw',dtype='<i2').astype(np.float32)/32768
def bp(x):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); X[(f<250)|(f>3500)]=0; return np.fft.irfft(X,len(x))
def env(x,hop):
    h=int(SR*hop); w=h*2 if hop>=0.005 else 40  # 5ms window min for fine
    w=max(w,h); n=(len(x)-w)//h
    sq=x*x; cs=np.concatenate([[0],np.cumsum(sq)])
    idx=np.arange(n)*h
    e=np.sqrt((cs[idx+w]-cs[idx])/w)+1e-6
    e=np.log(e); e-=np.median(e); return e
def xcorr(a,b):
    a=(a-a.mean())/a.std(); b=(b-b.mean())/b.std()
    N=1<<int(np.ceil(np.log2(len(a)+len(b))))
    c=np.fft.irfft(np.fft.rfft(a,N)*np.conj(np.fft.rfft(b,N)),N)
    return c,N
ref=bp(load('obs'))
out={}
for cam in ['camAVE','cam093A','camC0003']:
    x=bp(load(cam))
    # coarse 10ms
    ea,eb=env(ref,0.01),env(x,0.01)
    c,N=xcorr(ea,eb); k=int(np.argmax(c)); L=k if k<N//2 else k-N
    conf=c[k]/np.median(np.abs(c))
    T=L*0.01
    # fine 1ms, +-50ms
    def fine(T0,t0,dur,hop,rng):
        # ref window [t0,t0+dur], cam window at t0-T0
        hopn=int(SR*hop); w=int(SR*0.005)
        rs=int((t0)*SR); cs_=int((t0-T0)*SR)
        if cs_<int(rng*SR)+1 or rs<0: return None
        r=ref[rs:rs+int(dur*SR)]; 
        best=None
        lags=np.arange(-int(rng/hop),int(rng/hop)+1)
        er=None
        def e2(sig):
            sq=sig*sig; cs=np.concatenate([[0],np.cumsum(sq)]); n=(len(sig)-w)//hopn
            idx=np.arange(n)*hopn; return np.log(np.sqrt((cs[idx+w]-cs[idx])/w)+1e-6)
        er=e2(r); er=(er-er.mean())/er.std()
        seg=x[cs_-int(rng*SR)-hopn: cs_+int(dur*SR)+int(rng*SR)+hopn]
        if len(seg)<int(dur*SR)+2*int(rng*SR): return None
        es=e2(seg)
        base=(int(rng*SR)+hopn)//hopn
        sc=[]
        for l in lags:
            st=base-l
            s=es[st:st+len(er)]
            if len(s)<len(er): sc.append(-9);continue
            s=(s-s.mean())/s.std(); sc.append(float(np.dot(er,s)/len(er)))
        sc=np.array(sc); i=int(np.argmax(sc))
        return T0+lags[i]*hop, sc[i], float(np.median(sc))
    lenref=len(ref)/SR; lencam=len(x)/SR
    ov0=max(0,T); ov1=min(lenref,T+lencam)
    mid=(ov0+ov1)/2
    Tf,sf,_=fine(T,mid-60,120,0.001,0.05)
    # drift: 5 windows of 90s, 0.5ms hop, +-100ms
    wins=[]
    for frac in [0.05,0.27,0.5,0.73,0.95]:
        t0=ov0+(ov1-ov0-90)*frac
        r=fine(Tf,t0,90,0.0005,0.1)
        if r: wins.append((round(t0,1),round(r[0],4),round(r[1],3)))
    out[cam]=dict(coarse=T,conf=float(conf),fine=Tf,fine_score=sf,windows=wins,len=lencam)
    print(cam,json.dumps(out[cam]))
print('ref len',len(ref)/SR)
json.dump(out,open(f'{D}/offsets.json','w'),indent=1)
