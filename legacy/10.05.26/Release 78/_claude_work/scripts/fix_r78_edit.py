# usage: python3 fix_r78_edit.py IN.xml OUT.xml  -> re-stacks shifted angle tracks, centers TATTOO ONLY, card follows it
import xml.etree.ElementTree as ET, copy, sys
F=30000/1001
def tc(f): s=f/F; return f"{int(s//60)}:{s%60:05.2f}"
src,dst=sys.argv[1],sys.argv[2]
tree=ET.parse(src); r=tree.getroot(); main=r.find('sequence')
vt=main.findall('media/video/track')
CL=('clipitem','generatoritem','transitionitem')
# ---------- 1. restack: find where the stack jumped up a track ----------
SPLIT=min(int(c.findtext('start')) for c in vt[1] if c.tag=='clipitem' and c.findtext('name')=='ANG 1 NICK')
print('stack shifted up one track from main frame',SPLIT,tc(SPLIT))
moved={}
for k in range(1,len(vt)):
    items=[c for c in vt[k] if c.tag in CL and int(c.findtext('start'))>=SPLIT]
    for c in items: vt[k].remove(c)
    moved[k]=items
def insert_items(track,items):
    kids=list(track); last=max([i for i,c in enumerate(kids) if c.tag in CL],default=-1)
    for j,c in enumerate(items): track.insert(last+1+j,c)
for k in range(1,len(vt)): insert_items(vt[k-1],moved[k])
if not any(c.tag in CL for c in vt[-1]):
    main.find('media/video').remove(vt[-1]); print('removed empty top track')
vt=main.findall('media/video/track')
for i,t in enumerate(vt):
    names=sorted(set((c.findtext('name') or '')[:16] for c in t if c.tag=='clipitem' and int(c.findtext('start'))>=400))
    print(f' V{i+1}',names[:4])
# ---------- 2. center the TATTOO ONLY panel inside the ANG 8 nest ----------
def P(c,pid): 
    for p in c.iter('parameter'):
        if p.findtext('parameterid')==pid: return p
def setf(p,v): p.find('value').text=f'{v:.4f}'
ang8=next(s for s in r.iter('sequence') if s.findtext('name')=='R78 ANG 8 TATTOO ONLY' and s.find('media') is not None)
T=ang8.findall('media/video/track')
mattes=[]
for c in T[2].findall('clipitem'):
    l=float(P(c,'leftcrop').find('value').text); rr=float(P(c,'rightcrop').find('value').text)
    x0=l*19.2; x1=1920-rr*19.2; mattes.append((int(c.findtext('start')),int(c.findtext('end')),960-(x0+x1)/2))
def dx_at(g):
    for a,b,d in mattes:
        if a<=g<b: return d
    return None
n=0
for ti in (1,2):            # white border plate, black matte: slide the crop window
    for c in T[ti].findall('clipitem'):
        d=dx_at(int(c.findtext('start')))
        if d is None: continue
        lp,rp=P(c,'leftcrop'),P(c,'rightcrop')
        setf(lp,float(lp.find('value').text)+d/19.2); setf(rp,float(rp.find('value').text)-d/19.2); n+=1
for c in T[5].findall('clipitem'):  # IG post / hold: move the center
    d=dx_at(int(c.findtext('start')))
    if d is None: continue
    cp=P(c,'center'); h=cp.find('value/horiz'); h.text=f'{float(h.text)+d/1920:.6f}'; n+=1
print('tattoo-only: recentered',n,'layers; shifts (px):',sorted(set(round(d) for a,b,d in mattes)))
# ---------- 3. handle card follows the panel during tattoo-only shots ----------
cardtr=next(t for t in vt if any((c.findtext('name') or '').startswith('@') for c in t))
tpl=copy.deepcopy(next(f for f in T[5].find('clipitem').findall('filter') if f.findtext('effect/effectid')=='basic'))
for p in tpl.iter('parameter'):
    pid=p.findtext('parameterid'); v=p.find('value')
    if pid=='scale': v.text='100'
    elif pid=='center': v.find('horiz').text='0'; v.find('vert').text='0'
    elif pid in('leftcrop','rightcrop','topcrop','bottomcrop'): v.text='0'
shots=[]
for t in vt:
    for c in t:
        if c.tag=='clipitem' and c.findtext('name')=='ANG 8 TATTOO ONLY' and c.findtext('enabled')=='TRUE':
            shots.append((int(c.findtext('start')),int(c.findtext('end')),dx_at(int(c.findtext('in')))))
print('enabled tattoo-only shots:',[(tc(a),tc(b),round(d or 0)) for a,b,d in shots])
def split(track,frame):
    for i,c in enumerate(list(track)):
        if c.tag!='clipitem': continue
        s,e=int(c.findtext('start')),int(c.findtext('end'))
        if s<frame<e:
            c2=copy.deepcopy(c); c2.set('id',c.get('id')+'-s'+str(frame))
            fe=c2.find('file')
            for ch in list(fe): fe.remove(ch)
            i0=int(c.findtext('in'))
            c.find('end').text=str(frame); c.find('out').text=str(i0+frame-s)
            c2.find('start').text=str(frame); c2.find('in').text=str(i0+frame-s)
            track.insert(list(track).index(c)+1,c2); return
for a,b,d in shots:
    if not d: continue
    split(cardtr,a); split(cardtr,b)
    for c in cardtr.findall('clipitem'):
        if int(c.findtext('start'))==a and (c.findtext('name') or '').startswith('@'):
            f=copy.deepcopy(tpl); P(f,'center').find('value/horiz').text=f'{d/1920:.6f}'; c.append(f)
tree.write(dst+'.tmp',encoding='unicode')
body=open(dst+'.tmp').read(); import os; os.remove(dst+'.tmp')
with open(dst,'w',encoding='utf-8') as f: f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'+body)
ET.parse(dst); print('wrote',dst)
