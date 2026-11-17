import numpy as np, json
SR=8000; hop=400  # 50ms
def lv(k):
    x=np.fromfile(f'{k}.raw','<i2').astype(np.float32)/32768
    # high-pass-ish: remove <100Hz via diff-ish FFT bandpass 150-3500
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); X[(f<150)|(f>3500)]=0; x=np.fft.irfft(X,len(x))
    n=len(x)//hop; return 20*np.log10(np.sqrt((x[:n*hop].reshape(n,hop)**2).mean(1))+1e-7)
L=np.stack([lv('m1'),lv('m2'),lv('m3')])
for i in range(3): print('mic',i+1,'p10 %.1f p50 %.1f p90 %.1f p98 %.1f'%tuple(np.percentile(L[i],[10,50,90,98])))
np.save('mic_levels.npy',L)
# bleed: when mic i is loudest by far, how much lower are others?
for i in range(3):
    m=L[i]>np.percentile(L[i],97)
    print('mic',i+1,'loud frames: others minus it', [round(float(np.median(L[j][m]-L[i][m])),1) for j in range(3)])
