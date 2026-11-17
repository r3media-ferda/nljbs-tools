import numpy as np, json
L=np.load('mic_levels.npy'); n=L.shape[1]
G=np.array([0,0,1.5])  # mic3 hotter
A=L-G[:,None]
o=np.argsort(-A,0); top=o[0]; mx=A.max(0); sec=np.sort(A,0)[-2]
lab=np.where(mx<-47,0,np.where(mx-sec>4,top+1,np.where(sec>-44,4,top+1)))  # 4 = overlap/crosstalk
# 0.5s bins
b=10; nb=n//b
lb=lab[:nb*b].reshape(nb,b)
cnt=np.stack([(lb==k).sum(1) for k in range(5)],1)
print('share of 50ms frames: sil %.2f m1 %.2f m2 %.2f m3 %.2f overlap %.2f'%tuple(cnt.sum(0)/cnt.sum()))
np.save('spk_cnt_05.npy',cnt)
# motion in 093A
g=np.fromfile('g093A_2fps.raw',np.uint8).reshape(-1,108,192).astype(np.int16)
m=np.abs(np.diff(g,axis=0))
left=m[:,15:75,20:80].mean((1,2)); right=m[:,15:75,100:160].mean((1,2))
k=min(len(left),nb-1)
s2=cnt[1:k+1,2]>=6; s3=cnt[1:k+1,3]>=6; s1=cnt[1:k+1,1]>=6
for nm,s in (('m1',s1),('m2',s2),('m3',s3)):
    print(nm,'talking: left motion %.2f right %.2f | not: left %.2f right %.2f'%(left[:k][s].mean(),right[:k][s].mean(),left[:k][~s].mean(),right[:k][~s].mean()))
