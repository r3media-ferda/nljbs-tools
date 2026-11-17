import numpy as np, json
g=np.fromfile('obs_10fps_g.raw',np.uint8).reshape(-1,72,128).astype(np.int16)
n=len(g); d=np.r_[0,np.abs(np.diff(g,axis=0)).mean((1,2))]
# chrome region (header/comments column right side) diff for IG: x>=1200 -> col 80+
dc=np.r_[0,np.abs(np.diff(g[:,6:,82:120],axis=0)).mean((1,2))]
act=d>0.3
runs=[];k=2800
while k<n:
    j=k
    while j<n and act[j]==act[k]: j+=1
    runs.append([k/10,j/10,bool(act[k]),float(d[k:j].mean()),float(dc[k:j].mean())]); k=j
# merge: still runs <0.8s inside active -> active
out=[]
for r in runs:
    if out and (not r[2]) and r[1]-r[0]<0.8: r[2]=True
    if out and out[-1][2]==r[2]: out[-1][1]=r[1]; out[-1][3]=max(out[-1][3],r[3]); out[-1][4]=max(out[-1][4],r[4])
    else: out.append(r)
for r in out:
    if r[2]: print(f'ACT  {r[0]:7.1f}-{r[1]:7.1f} ({r[1]-r[0]:5.1f}) d {r[3]:5.1f} chrome {r[4]:5.1f}')
    else: print(f'still {r[0]:7.1f}-{r[1]:7.1f} ({r[1]-r[0]:5.1f})')
json.dump(out,open('runs.json','w'))
