import numpy as np
W,H=480,270
a=np.memmap('obs_2fps.rgb',np.uint8,'r'); n=len(a)//(W*H*3); a=a[:n*W*H*3].reshape(n,H,W,3)
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
g=np.fromfile('obs_10fps_g.raw',np.uint8).reshape(-1,72,128).astype(np.int16)
d=np.abs(np.diff(g,axis=0))  # 10fps diffs
np.save('B.npy',np.array([b if b else [-1]*4 for b in B]))
for i in range(560,n,2):
    t=i/2; b=B[i]
    k=int(t*10); seg=d[k:k+10]
    if b:
        x0,x1,y0,y1=[v//15 for v in b]  # to 128x72
        m=np.zeros((72,128),bool); m[y0:y1,x0:x1]=True
        din=seg[:,m].mean(); dout=seg[:,~m].mean()
    else: din=-1; dout=seg.mean()
    print(f'{t:6.0f} {str(b):26s} in {din:5.1f} out {dout:5.1f}')
