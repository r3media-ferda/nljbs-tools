import json, xml.etree.ElementTree as ET, os, numpy as np
from collections import Counter
H=os.path.expanduser; FPS=30000/1001; INTRO=400
NAMES=['ANG 1 NICK','ANG 2 ANDREW + PORTER','ANG 3 WIDE','ANG 4 SPLIT - NICK + TATTOO','ANG 5 SPLIT - GUESTS + TATTOO','ANG 6 TATTOO + NICK PIP','ANG 7 TATTOO + GUESTS PIP','ANG 8 TATTOO ONLY','ANG 9 NICK TIGHT','ANG 10 GUESTS TIGHT']
def pick(s):
    if s['mode']=='F': return {'AVE':8 if s['punch'] else 0,'093A':9 if s['punch'] else 1,'C':2}[s['cam']]
    if s['mode']=='A': return 3 if s['cam']=='AVE' else 4
    if s['mode']=='T': return 7
    return 5 if s['cam']=='AVE' else 6
def per_g(plan):
    NB=plan['NF']-INTRO; arr=np.full(NB,-1,int)
    for s in plan['segs']: arr[s['fa']-INTRO:s['fb']-INTRO]=pick(s)
    return arr
v2=per_g(json.load(open('plan_v2.json'))); v3=per_g(json.load(open('plan_v3.json'))); NB=len(v2)
r=ET.parse(H('~/mnt/release 77/ShopTalk_10-05-26_R77_SWITCHER_v2.xml')).getroot(); main=r.find('sequence')
user=np.full(NB,-1,int); tmap=np.full(NB,-1,int); toptrack=np.full(NB,-1,int)
for ti,tr in enumerate(main.findall('media/video/track')[:10]):
    for c in tr.findall('clipitem'):
        nm=c.findtext('name')
        if nm not in NAMES: continue
        s,e,i=int(c.findtext('start')),int(c.findtext('end')),int(c.findtext('in'))
        if s<0 or e<0: continue
        g0,g1=i,i+(e-s)
        if g1>NB: g1=NB
        tmap[g0:g1]=np.arange(s,s+(g1-g0))
        if c.findtext('enabled')=='TRUE':
            seg=slice(g0,g1); upd=toptrack[seg]<=ti
            user[seg]=np.where(upd,NAMES.index(nm),user[seg]); toptrack[seg]=np.where(upd,ti,toptrack[seg])
removed=tmap<0
changed=(user!=v2)&(user>=0)&~removed
nothing=(user<0)&~removed
def ranges(mask):
    out=[]; i=0
    while i<len(mask):
        if mask[i]:
            j=i
            while j<len(mask) and mask[j]: j+=1
            out.append((i,j)); i=j
        else: i+=1
    return out
def mmss(g): t=(g+INTRO)/FPS; return f'{int(t//60)}:{t%60:05.2f}'
print('removed ranges (source):'); [print('  ',mmss(a),'-',mmss(b),f'({(b-a)/FPS:.1f}s)') for a,b in ranges(removed)]
print('no angle enabled (black) ranges:'); [print('  ',mmss(a),'-',mmss(b),f'({(b-a)/FPS:.1f}s)') for a,b in ranges(nothing) if b-a>3]
print('your angle changes:')
for a,b in ranges(changed):
    if b-a<3: continue
    print(f'   {mmss(a)}-{mmss(b)} ({(b-a)/FPS:.1f}s): {NAMES[Counter(v2[a:b]).most_common(1)[0][0]]} -> {NAMES[Counter(user[a:b]).most_common(1)[0][0]]}')
np.savez('user_edits.npz',user=user,removed=removed,changed=changed,v2=v2,v3=v3)
