import numpy as np, wave, json
def load(f):
    w=wave.open(f); return np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768
M=[load(f'au/{f}') for f in ['Mic_1_53_16k.wav','Mic_2_53_16k.wav','Mic_3_54_16k.wav']]
n=min(len(m) for m in M)//800
L=[]
for m in M:
    X=np.fft.rfft(m[:n*800].reshape(n,800)*np.hanning(800),axis=1); f=np.fft.rfftfreq(800,1/16000)
    band=(f>150)&(f<3500); p=(np.abs(X[:,band])**2).sum(1)/ (800*800/4)
    L.append(10*np.log10(p+1e-12))
L=np.array(L); L[2]-=1.5
top=L.argmax(0); mx=L.max(0); sec=np.sort(L,0)[-2]
lab=np.where((mx>-47)&(mx-sec>4),top+1,0)
json.dump(dict(hop=0.05,lab=lab.tolist(),lev=np.round(L,1).tolist()),open('spk.json','w'))
from collections import Counter; print(Counter(lab.tolist()), n*0.05)
