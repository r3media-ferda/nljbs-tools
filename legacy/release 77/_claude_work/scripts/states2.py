import numpy as np, os, json
D=os.path.expanduser('~/r77'); W,H=480,270
def bbox(fr):
    lum=fr.astype(np.int16).mean(2); band=lum[75:200]
    cm=band.mean(0); cs=band.std(0)
    cols=np.where((cm>40)&(cs>12))[0]
    cols=cols[(cols>20)&(cols<470)]
    if len(cols)<20: return None
    runs=np.split(cols,np.where(np.diff(cols)>2)[0]+1); r=max(runs,key=len)
    if len(r)<40: return None
    x0,x1=r[0],r[-1]
    rm=lum[12:,x0+4:x1-4].mean(1); rows=np.where(rm>35)[0]+12
    if len(rows)<40: return None
    rr=np.split(rows,np.where(np.diff(rows)>2)[0]+1); q=max(rr,key=len)
    return [int(x0)*4,int(x1+1)*4,int(q[0])*4,int(q[-1]+1)*4]
a=np.memmap(f'{D}/obs_2fps.rgb',np.uint8,'r'); n=len(a)//(W*H*3); a=a[:n*W*H*3].reshape(n,H,W,3)
REEL=[704,1256,84,1068]
def snap(b):
    if b is None: return None
    ar=(b[1]-b[0])/max(1,b[3]-b[2])
    if ar<0.6 and b[0]>=660 and b[1]<=1300 and b[3]-b[2]>900: return REEL
    return b
start=1034  # 517 s
B=[snap(bbox(a[i])) for i in range(n)]
diff=np.r_[0,[float(np.abs(a[i,20:260:3,20:460:3].astype(np.int16)-a[i-1,20:260:3,20:460:3]).mean()) for i in range(1,n)]]
print('diff pct in reels phase',np.percentile(diff[2140:],[50,75,90,95,98]).round(1))
runs=[];cur=None;miss=0
for i in range(start,n):
    b=B[i]; spike=diff[i]>38
    if cur and not spike and (b is None and miss<1 or b is not None and all(abs(b[k]-cur['b'][k])<=24 for k in range(4))):
        cur['e']=i+1; miss=miss+1 if b is None else 0
        if b is not None: cur['bs'].append(b)
    else:
        if cur: runs.append(cur)
        cur=dict(s=i,e=i+1,b=b,bs=[b]) if (b is not None and not spike) else None; miss=0
if cur: runs.append(cur)
st=[]
for r in runs:
    if (r['e']-r['s'])/2<2.5: continue
    b=np.median(np.array(r['bs']),0).astype(int).tolist()
    st.append(dict(t0=r['s']/2,t1=r['e']/2,box=b))
tot=sum(s['t1']-s['t0'] for s in st)
print('states',len(st),'cover',tot,'of',(n-start)/2)
json.dump(dict(start=start/2,states=st),open(f'{D}/states.json','w'))
from collections import Counter
print(Counter(tuple(s['box']) for s in st).most_common(8))
for s in st: 
    b=s['box']; print(f"{s['t0']:7.1f}-{s['t1']:7.1f} ({s['t1']-s['t0']:5.1f}s) x{b[0]}-{b[1]} y{b[2]}-{b[3]} ar {(b[1]-b[0])/(b[3]-b[2]):.2f}")
