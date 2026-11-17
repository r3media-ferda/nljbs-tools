import numpy as np, wave, sys, json, os, time
from multiprocessing import Pool
from pocketsphinx import Decoder
D=os.path.dirname(os.path.abspath(__file__))
w=wave.open(os.path.join(D,'Left_Audio_Channel_54_16k.wav')); x=np.frombuffer(w.readframes(w.getnframes()),np.int16)
e=np.sqrt((x[:len(x)//160*160].reshape(-1,160).astype(float)**2).mean(1))
cuts=[0]; t=1500
while t<len(e)-500:
    w0=t-300; k=w0+int(np.argmin(e[w0:t+300])); cuts.append(k); t=k+1500
cuts.append(len(e)); chunks=list(enumerate(zip(cuts[:-1],cuts[1:])))
OUT=os.path.join(D,'asr'); os.makedirs(OUT,exist_ok=True)
def run(c):
    i,(a,b)=c; fn=f'{OUT}/{i:03d}.json'
    if os.path.exists(fn): return
    d=Decoder(samprate=16000)
    d.start_utt(); d.process_raw(x[a*160:b*160].tobytes(),full_utt=True); d.end_utt()
    out=[(s.word.split('(')[0].lower(),(a+s.start_frame)/100,(a+s.end_frame)/100) for s in d.seg() if not s.word.startswith(('<','['))]
    json.dump(out,open(fn,'w'))
if __name__=='__main__':
    t0=time.time(); todo=[c for c in chunks if not os.path.exists(f'{OUT}/{c[0]:03d}.json')]
    with Pool(4) as p:
        for _ in p.imap_unordered(run,todo):
            if time.time()-t0>150: p.terminate(); break
    print(len(chunks),'chunks, done',len(os.listdir(OUT)))
