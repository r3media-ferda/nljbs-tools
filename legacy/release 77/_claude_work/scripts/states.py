import numpy as np, os, json, subprocess
D=os.path.expanduser('~/r77'); W,H=480,270; FPS2=2
a=np.memmap(f'{D}/obs_2fps.rgb',np.uint8,'r'); n=len(a)//(W*H*3); a=a[:n*W*H*3].reshape(n,H,W,3)
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
B=[bbox(a[i]) for i in range(n)]
diff=np.r_[0,[float(np.abs(a[i,20:260:3,20:460:3].astype(np.int16)-a[i-1,20:260:3,20:460:3]).mean()) for i in range(1,n)]]
# active start: first big change after 60s of stillness
start=next(i for i in range(n) if diff[i]>6 and i>20)
print('screen activity starts at',start/2,'s')
# group stable bbox runs
runs=[]; cur=None
for i in range(start,n):
    b=B[i]
    ok=b is not None and diff[i]<25
    if ok and cur and all(abs(b[k]-cur['b'][k])<=16 for k in range(4)):
        cur['e']=i+1; cur['bs'].append(b)
    else:
        if cur: runs.append(cur)
        cur=dict(s=i,e=i+1,b=b,bs=[b]) if ok else None
if cur: runs.append(cur)
st=[]
for r in runs:
    dur=(r['e']-r['s'])/FPS2
    if dur<2.5: continue
    b=np.median(np.array(r['bs']),0).astype(int).tolist()
    st.append(dict(t0=r['s']/FPS2,t1=r['e']/FPS2,box=b))
print('stable states',len(st),'covering',round(sum(s['t1']-s['t0'] for s in st),1),'s of',round((n-start)/2,1))
json.dump(dict(start=start/2,states=st),open(f'{D}/states.json','w'))
for s in st[:80]: 
    b=s['box']; print(f"{s['t0']:7.1f}-{s['t1']:7.1f} ({s['t1']-s['t0']:5.1f}s) box x{b[0]}-{b[1]} y{b[2]}-{b[3]} ar {(b[1]-b[0])/(b[3]-b[2]):.2f}")
