import json, re, wave, numpy as np, difflib, glob, sys
from pocketsphinx import Decoder
from multiprocessing import Pool
P={p['id']:p for p in json.load(open('plan.json'))}
norm=lambda s: re.sub(r"[^a-z0-9]","",s.lower())
D='/mnt/user-data/uploads/WORKING SHOP TALM FILES/10.05.26/Release 78/_claude_work/reels/chkau/'
def run(rid):
    f=glob.glob(D+f'R78_{rid}_*.wav')[0]; w=wave.open(f); x=np.frombuffer(w.readframes(w.getnframes()),np.int16)
    d=Decoder(samprate=16000,lm='shoptalk.lm',lw=4.0)
    out=[]
    for a in range(0,len(x),16000*12):
        d.start_utt(); d.process_raw(x[a:a+16000*12].tobytes(),full_utt=True); d.end_utt()
        try: out+=[(norm(s.word.split('(')[0]),a/16000+s.start_frame/100) for s in d.seg() if not s.word.startswith(('<','['))]
        except TypeError: pass
    toks=[(norm(t['t']),t['s']) for c in P[rid]['cap'] for t in c['toks']]
    sm=difflib.SequenceMatcher(None,[t[0] for t in toks],[o[0] for o in out],autojunk=False)
    diffs=[]
    for b in sm.get_matching_blocks():
        if b.size>=2:
            for k in range(b.size): diffs.append(out[b.b+k][1]-toks[b.a+k][1])
    diffs=np.array(diffs)
    # offsets over time
    return rid,len(toks),len(diffs),round(float(np.median(diffs)),2) if len(diffs) else None, round(float(np.percentile(np.abs(diffs),80)),2) if len(diffs) else None
with Pool(2) as p:
    for r in p.map(run,sorted(P)): print(r)
