import json, re, wave, numpy as np, difflib, glob
from pocketsphinx import Decoder
from multiprocessing import Pool
plan=json.load(open('plan.json'))
norm=lambda s: re.sub(r"[^a-z0-9]","",s.lower())
D='/mnt/user-data/uploads/WORKING SHOP TALM FILES/10.05.26/Release 78/_claude_work/reels/chkau/'
def asr(rid):
    f=glob.glob(D+f'R78_{rid}_*.wav')[0]; w=wave.open(f); x=np.frombuffer(w.readframes(w.getnframes()),np.int16)
    out=[]
    for a in range(0,len(x),16000*12):
        for lw in (4.0,):
            d=Decoder(samprate=16000,lm='shoptalk.lm',lw=lw)
            d.start_utt(); d.process_raw(x[a:a+16000*12+8000].tobytes(),full_utt=True); d.end_utt()
            try: out+=[(norm(s.word.split('(')[0]),a/16000+s.start_frame/100,a/16000+s.end_frame/100) for s in d.seg() if not s.word.startswith(('<','[')) and a/16000+s.start_frame/100 < a/16000+12]
            except TypeError: pass
    return rid,out
with Pool(2) as p: A=dict(p.map(asr,[q['id'] for q in plan]))
for P in plan:
    toks=[t for c in P['cap'] for t in c['toks']]
    out=A[P['id']]
    sm=difflib.SequenceMatcher(None,[norm(t['t']) for t in toks],[o[0] for o in out],autojunk=False)
    m={}
    for b in sm.get_matching_blocks():
        if b.size>=2:
            for k in range(b.size):
                o=out[b.b+k]; t=toks[b.a+k]
                if abs(o[1]-t['s'])<1.5: m[b.a+k]=(o[1],o[2])
    ks=sorted(m); moved=[]
    for i,t in enumerate(toks):
        if i in m: moved.append(m[i][0]-t['s']); t['s'],t['e']=m[i]
        elif ks:
            lo=max([k for k in ks if k<i],default=None); hi=min([k for k in ks if k>i],default=None)
            if lo is not None and hi is not None:
                # keep original spacing, shift by interpolated correction
                pass
    # interpolate shift for unmatched tokens
    sh=np.array([m[k][0] for k in ks]) if ks else None
    for c in P['cap']:
        c['s']=c['toks'][0]['s']
    P['cap'].sort(key=lambda c:c['s'])
    for j,c in enumerate(P['cap']):
        end=max(c['toks'][-1]['e']+0.25,c['s']+0.45)
        if j+1<len(P['cap']): end=min(end,P['cap'][j+1]['s'])
        c['e']=min(end,P['dur'])
    print(P['id'],'matched',len(m),'of',len(toks),'median shift',round(float(np.median(moved)),2) if moved else None,'p80',round(float(np.percentile(np.abs(moved),80)),2) if moved else None)
json.dump(plan,open('plan.json','w'),indent=0)
