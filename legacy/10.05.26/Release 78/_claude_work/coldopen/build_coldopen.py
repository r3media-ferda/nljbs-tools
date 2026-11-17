import xml.etree.ElementTree as ET, copy, sys
F=30000/1001
def fr(sec): return int(round(sec*F))
def nest_in(m): return fr(m)-400
src,dst=sys.argv[1],sys.argv[2]
R=ET.parse(src).getroot(); main=R.find('sequence')
fdefs={};sdefs={}
for e in R.iter('file'):
    if len(e) and e.get('id') not in fdefs: fdefs[e.get('id')]=e
for e in R.iter('sequence'):
    if e.get('id') and e.find('media') is not None and e is not main: sdefs[e.get('id')]=e
def tpl_nest(name):
    for t in main.findall('media/video/track'):
        for c in t.findall('clipitem'):
            if c.findtext('name')==name: return c
def tpl_audio(k):
    t=main.findall('media/audio/track')[k]
    return next(c for c in t.findall('clipitem') if c.findtext('name','').startswith('MIC'))
V12=main.findall('media/video/track')[11]
def card_tpl(h): return next(c for c in V12.findall('clipitem') if c.findtext('name')=='@'+h)
slid=next(c for c in V12.findall('clipitem') if c.find("filter/effect[effectid='basic']") is not None)
basic=copy.deepcopy(next(f for f in slid.findall('filter') if f.findtext('effect/effectid')=='basic'))
uid=[0]
def item(tpl,start,end,inn,enabled=True):
    c=copy.deepcopy(tpl); uid[0]+=1; c.set('id',f'co-{uid[0]}')
    for l in c.findall('link'): c.remove(l)
    c.find('start').text=str(start); c.find('end').text=str(end)
    c.find('in').text=str(inn); c.find('out').text=str(inn+end-start)
    if c.find('enabled') is not None: c.find('enabled').text='TRUE' if enabled else 'FALSE'
    return c
ANG={'NICK':'ANG 1 NICK','GUESTS':'ANG 2 ANDREW + PORTER','TATTOO':'ANG 8 TATTOO ONLY','GTIGHT':'ANG 10 GUESTS TIGHT'}
AUD=[(1093.55,1099.30),(1087.55,1092.75),(1011.30,1013.70),(1013.95,1017.25),(1022.82,1028.65),(716.02,720.35)]
lens=[fr(b)-fr(a) for a,b in AUD]
starts=[sum(lens[:i]) for i in range(len(lens))]; TOT=sum(lens)
s0,s1,s2,s3,s4,s5=starts
punch=s0+(fr(1097.20)-fr(1093.55))
VID=[(s0,punch,'GUESTS',1093.55,None,0),(punch,s1,'GTIGHT',1097.20,None,0),(s1,s2,'NICK',1087.55,None,0),
     (s2,s5,'TATTOO',1011.30,'stewart_modernclassic',-650.3),(s5,TOT,'TATTOO',617.60,'tiger_ramos',-500.7)]
seq=ET.Element('sequence',id='r78-coldopen')
ET.SubElement(seq,'name').text='R78 COLD OPEN'
ET.SubElement(seq,'duration').text=str(TOT)
seq.append(copy.deepcopy(main.find('rate')))
if main.find('timecode') is not None: seq.append(copy.deepcopy(main.find('timecode')))
media=ET.SubElement(seq,'media'); vid=ET.SubElement(media,'video'); vid.append(copy.deepcopy(main.find('media/video/format')))
t1=ET.SubElement(vid,'track'); t2=ET.SubElement(vid,'track')
for a,b,ang,m,card,dx in VID:
    t1.append(item(tpl_nest(ANG[ang]),a,b,nest_in(m)))
    if card:
        c=item(card_tpl(card),a,b,0)
        for f in c.findall('filter'): c.remove(f)
        f=copy.deepcopy(basic)
        for p in f.iter('parameter'):
            pid=p.findtext('parameterid'); v=p.find('value')
            if pid=='scale': v.text='100'
            elif pid=='center': v.find('horiz').text=f'{dx/1920:.6f}'; v.find('vert').text='0'
            elif pid in('leftcrop','rightcrop','topcrop','bottomcrop'): v.text='0'
        c.append(f); t2.append(c)
for t in (t1,t2): ET.SubElement(t,'enabled').text='TRUE'; ET.SubElement(t,'locked').text='FALSE'
aud=ET.SubElement(media,'audio')
mf=main.find('media/audio/format')
if mf is not None: aud.append(copy.deepcopy(mf))
for k in (0,2,4):
    tr=ET.SubElement(aud,'track'); tp=tpl_audio(k)
    for (a,b),st in zip(AUD,starts): tr.append(item(tp,st,st+fr(b)-fr(a),fr(a)))
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
seen_f=set(); seen_s=set()
def walk(e):
    for ch in list(e):
        if ch.tag=='file' and ch.get('id'):
            i=ch.get('id')
            if i in seen_f:
                for g in list(ch): ch.remove(g)
            else:
                seen_f.add(i)
                if len(ch)==0 and i in fdefs:
                    for g in fdefs[i]: ch.append(copy.deepcopy(g))
        elif ch.tag=='sequence' and ch.get('id') and e.tag=='clipitem':
            i=ch.get('id')
            if i in seen_s:
                for g in list(ch): ch.remove(g)
                continue
            seen_s.add(i)
            if ch.find('media') is None and i in sdefs:
                for g in list(ch): ch.remove(g)
                for g in sdefs[i]: ch.append(copy.deepcopy(g))
        walk(ch)
walk(seq)
root=ET.Element('xmeml',version=R.get('version','4')); root.append(seq)
body=ET.tostring(root,encoding='unicode')
open(dst,'w',encoding='utf-8').write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'+body)
ET.parse(dst)
def tc(f): s=f/F; return f"{int(s//60)}:{s%60:05.2f}"
print('wrote',dst,'frames',TOT,tc(TOT))
for a,b,ang,m,card,dx in VID: print(' V',tc(a),'-',tc(b),ang,'@mic',m,card or '')
print('nests:',sorted(seen_s),'files:',len(seen_f))
undef=[f.get('id') for f in root.iter('file') if len(f)==0]
print('empty file refs (should be later uses only):',len(undef))
