import json, re, numpy as np, wave, os
from pocketsphinx import Decoder
import pocketsphinx
DICT=set(l.split()[0].split('(')[0] for l in open(os.path.join(os.path.dirname(pocketsphinx.__file__),'model','en-us','cmudict-en-us.dict')))
words=json.load(open('words_t.json')); R=json.load(open('specs.json'))
w=wave.open('au/Left_Audio_Channel_54_16k.wav'); x=np.frombuffer(w.readframes(w.getnframes()),np.int16)
norm=lambda s: re.sub(r"[^a-z0-9']","",s.lower())
def align(i0,i1,pad):
    t0=max(0,words[i0]['s']-pad); t1=words[i1]['e']+pad
    idx=[i for i in range(i0,i1+1) if norm(words[i]['w']) in DICT]
    d=Decoder(samprate=16000,beam=1e-80,wbeam=1e-60)
    d.set_align_text(' '.join(norm(words[i]['w']) for i in idx))
    d.start_utt(); d.process_raw(x[int(t0*16000):int(t1*16000)].tobytes(),full_utt=True); d.end_utt()
    seg=[s for s in d.seg() if not s.word.startswith(('<','['))]
    if len(seg)!=len(idx): return None
    return {i:(t0+s.start_frame/100,t0+(s.end_frame+1)/100) for i,s in zip(idx,seg)}
fixed={}; stats=[]
done=set()
for r in R:
    for a,b in r['body']:
        if (a,b) in done: continue
        done.add((a,b)); ok=0
        # sentence-ish chunks of <=12 words
        chunks=[];c0=a
        for i in range(a,b+1):
            if i==b or (words[i]['p'] and i-c0>=3) or i-c0>=11: chunks.append((c0,i)); c0=i+1
        for c0,c1 in chunks:
            res=None
            for pad in (0.8,1.5,2.5):
                try: res=align(c0,c1,pad)
                except Exception: res=None
                if res: break
            if res: fixed.update(res); ok+=c1-c0+1
        stats.append((r['id'],b-a+1,ok))
print(stats)
# merge: aligned words get exact times; others interpolate between nearest aligned in same range
for i,(s,e) in fixed.items(): words[i]['s'],words[i]['e']=round(s,2),round(e,2); words[i]['fa']=True
for a,b in done:
    ks=[i for i in range(a,b+1) if i in fixed]
    if len(ks)<2: continue
    for i in range(a,b+1):
        if i in fixed: continue
        lo=max([k for k in ks if k<i],default=None); hi=min([k for k in ks if k>i],default=None)
        if lo is not None and hi is not None:
            f=(i-lo)/(hi-lo); words[i]['s']=round(words[lo]['e']+(words[hi]['s']-words[lo]['e'])*f,2); words[i]['e']=round(words[i]['s']+0.15,2)
json.dump(words,open('words_r.json','w'))
