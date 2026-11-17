import numpy as np, wave, sys, json, os, time
from multiprocessing import Pool
from pocketsphinx import Decoder
D=os.path.dirname(os.path.abspath(__file__))
W=sys.argv[1]; LM=os.path.join(D,'shoptalk.lm'); OUT=os.path.join(D,'asr_lm'); os.makedirs(OUT,exist_ok=True)
w=wave.open(W); x=np.frombuffer(w.readframes(w.getnframes()),np.int16)
e=np.sqrt((x[:len(x)//160*160].reshape(-1,160).astype(float)**2).mean(1))
cuts=[0]; t=1000
while t<len(e)-400:
    w0=t-250; k=w0+int(np.argmin(e[w0:t+250])); cuts.append(k); t=k+1000
cuts.append(len(e)); chunks=list(enumerate(zip(cuts[:-1],cuts[1:])))
T0=float(sys.argv[2]) if len(sys.argv)>2 else 0; T1=float(sys.argv[3]) if len(sys.argv)>3 else 1e9
def run(c):
    i,(a,b)=c; fn=f'{OUT}/{i:03d}.json'
    if os.path.exists(fn): return
    d=Decoder(samprate=16000,lm=LM,lw=4.0,wip=0.5)
    d.start_utt(); d.process_raw(x[a*160:b*160].tobytes(),full_utt=True); d.end_utt()
    try: out=[(s.word.split('(')[0].lower(),(a+s.start_frame)/100,(a+s.end_frame)/100) for s in d.seg() if not s.word.startswith(('<','['))]
    except TypeError: out=[]
    json.dump(out,open(fn,'w'))
if __name__=='__main__':
    t0=time.time(); todo=[c for c in chunks if not os.path.exists(f'{OUT}/{c[0]:03d}.json') and c[1][1]/100>T0 and c[1][0]/100<T1]
    with Pool(int(os.environ.get('NP',4))) as p:
        for _ in p.imap_unordered(run,todo):
            if time.time()-t0>150: p.terminate(); break
    print(len(chunks),'chunks, done',len(os.listdir(OUT)))
