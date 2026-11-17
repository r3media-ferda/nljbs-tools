# remake80.py — rebuild Avery's edited R80 sequence (xmlforedits.xml) on the GarageBand mic exports.
#  - keeps every video edit he made (angles, cuts, cards) untouched
#  - audio: A1 MIC 1 PORTER / A2 MIC 2 AC / A3 MIC 3 JAKE (mono tracks, channel 1 of the dual-mono exports)
#           A4 SHOP TALK SCRATCH (one stereo pair) / A5 SHOP TALK BEAT (one stereo pair) — the 16-track stack is gone
#  - adds the @jake_hock outro graphic (copy of @aeconner, text patched in the title blob)
# usage: python3 remake80.py IN.xml OUT.xml X1 X2 X3 SR CH   (Xn = seconds into export n where raw mic time 0 sits)
import sys, copy, base64, struct, xml.etree.ElementTree as ET
from urllib.parse import quote
IN,OUT=sys.argv[1],sys.argv[2]; X=[float(v) for v in sys.argv[3:6]]; SR=int(sys.argv[6]); CH=int(sys.argv[7])
FPS=30000/1001; TK=8475667200
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 2/'
MICS=[('MIC 1 PORTER','mic 1.wav'),('MIC 2 AC','mic2.wav'),('MIC 3 JAKE','mic3.wav')]
B0=100.80
tree=ET.parse(IN); r=tree.getroot(); s=r.find('sequence'); med=s.find('media')
aud=med.find('audio'); atr=aud.findall('track')
# ---- collect mic clips + one stereo pair of each intro music file ----
mic={n:[] for n,_ in MICS}; music={}
for ti,tr in enumerate(atr):
    for c in tr.findall('clipitem'):
        nm=c.findtext('name') or ''
        if nm in mic: mic[nm].append(c)
        elif nm.startswith('SHOP TALK'):
            st=c.findtext('sourcetrack/trackindex')
            music.setdefault(nm,{}).setdefault(st,c)
for n in mic: mic[n].sort(key=lambda c:int(c.findtext('start')))
print({n:len(v) for n,v in mic.items()},{k:sorted(v) for k,v in music.items()})
# ---- tracks ----
tattr=dict(atr[0].attrib)
for tr in atr: aud.remove(tr)
def newtrack(ptype,expl=0,total=1,outch=1):
    t=ET.SubElement(aud,'track',dict(tattr)); t.set('premiereTrackType',ptype); t.set('currentExplodedTrackIndex',str(expl)); t.set('totalExplodedTrackCount',str(total))
    return t
def rate():
    e=ET.Element('rate'); ET.SubElement(e,'timebase').text='30'; ET.SubElement(e,'ntsc').text='TRUE'; return e
DUR=None
for k,(nm,fn) in enumerate(MICS):
    t=newtrack('Mono'); XF=int(round(X[k]*FPS)); first=True
    for i,c in enumerate(mic[nm]):
        cc=copy.deepcopy(c); cc.set('id',f'r80m{k+1}-{i}')
        for l in cc.findall('link'): cc.remove(l)
        for f in list(cc.findall('filter')):
            if f.findtext('effect/name')!='Audio Levels': cc.remove(f)
        i0=int(cc.findtext('in'))+XF; i1=int(cc.findtext('out'))+XF
        cc.find('in').text=str(i0); cc.find('out').text=str(i1)
        for tg,v in (('pproTicksIn',i0*TK),('pproTicksOut',i1*TK)):
            if cc.find(tg) is not None: cc.find(tg).text=str(v)
        fe=cc.find('file'); j=list(cc).index(fe); cc.remove(fe)
        fe=ET.Element('file',id=f'r80-mic{k+1}-export')
        if first:
            ET.SubElement(fe,'name').text=fn; ET.SubElement(fe,'pathurl').text='file://localhost'+quote(BASE+fn); fe.append(rate())
            ET.SubElement(fe,'duration').text=str(int(1803*FPS))
            a=ET.SubElement(ET.SubElement(fe,'media'),'audio'); sc=ET.SubElement(a,'samplecharacteristics')
            ET.SubElement(sc,'depth').text='16'; ET.SubElement(sc,'samplerate').text=str(SR); ET.SubElement(a,'channelcount').text=str(CH)
            first=False
        cc.insert(j,fe)
        st=cc.find('sourcetrack')
        if st is None: st=ET.SubElement(cc,'sourcetrack'); ET.SubElement(st,'mediatype').text='audio'; ET.SubElement(st,'trackindex')
        st.find('trackindex').text='1'
        t.append(cc)
    ET.SubElement(t,'enabled').text='TRUE'; ET.SubElement(t,'locked').text='FALSE'
# music: one stereo pair each, linked L/R
ti=4
for nm in sorted(music):
    pair=music[nm]; ids=[]
    lvl=next(p.findtext('value') for f in pair['1'].findall('filter') if f.findtext('effect/name')=='Audio Levels' for p in f.iter('parameter') if p.findtext('parameterid')=='level')
    for side,src in enumerate(['1','2']):
        c=pair[src] if src in pair else pair['1']
        cc=copy.deepcopy(c); cc.set('id',f'r80mus-{ti}-{side}'); ids.append(cc.get('id'))
        st=cc.find('sourcetrack'); st.find('trackindex').text=src
        for f in cc.findall('filter'):
            if f.findtext('effect/name')=='Audio Levels':
                for p in f.iter('parameter'):
                    if p.findtext('parameterid')=='level': p.find('value').text=lvl
        for l in cc.findall('link'): cc.remove(l)
        t=newtrack('Stereo',side,2); t.append(cc); ET.SubElement(t,'enabled').text='TRUE'; ET.SubElement(t,'locked').text='FALSE'
    for side,cid in enumerate(ids):
        c=aud.findall('track')[-2+side].find('clipitem')
        for k2,oid in enumerate(ids):
            l=ET.SubElement(c,'link'); ET.SubElement(l,'linkclipref').text=oid; ET.SubElement(l,'mediatype').text='audio'
            ET.SubElement(l,'trackindex').text=str(len(aud.findall('track'))-1+k2); ET.SubElement(l,'clipindex').text='1'; ET.SubElement(l,'groupindex').text='1'
    ti+=2
# make sure every music clip carries its file definition at least once
seen=set()
for c in aud.iter('clipitem'):
    fe=c.find('file')
    if fe is None: continue
    if len(fe)==0 and fe.get('id') not in seen:
        src=next((f for f in r.iter('file') if f.get('id')==fe.get('id') and len(f)),None)
        if src is not None: j=list(c).index(fe); c.remove(fe); c.insert(j,copy.deepcopy(src))
    seen.add(fe.get('id'))
# ---- @jake_hock outro graphic (his timeline: map body frames via the V1 angle nests) ----
v=med.find('video').findall('track')
nests=[(int(c.findtext('start')),int(c.findtext('end')),int(c.findtext('in'))) for c in v[0].findall('clipitem') if (c.findtext('name') or '').startswith('ANG ')]
def main_of(m):
    g=int(round((m-B0)*FPS))
    for a,b,i0 in nests:
        if i0<=g<i0+(b-a): return a+g-i0
    return None
ja,jb=main_of(1454.8),main_of(1460.3)
v12=v[11]; src=next(c for c in v12.findall('clipitem') if c.findtext('name')=='Graphic' and c.find('filter/effect/name').text=='@aeconner')
g=copy.deepcopy(src); g.set('id','r80gfx-jake_hock')
for l in g.findall('link'): g.remove(l)
i0=int(g.findtext('in')); g.find('start').text=str(ja); g.find('end').text=str(jb); g.find('out').text=str(i0+jb-ja)
for tg,vv in (('pproTicksIn',i0*TK),('pproTicksOut',(i0+jb-ja)*TK)):
    if g.find(tg) is not None: g.find(tg).text=str(vv)
fe=g.find('file')
if fe is not None and len(fe): [fe.remove(ch) for ch in list(fe)]
for f in g.findall('filter'):
    if f.findtext('effect/name')=='@aeconner': f.find('effect/name').text='@jake_hock'
    for p in f.iter('parameter'):
        if p.findtext('name')=='Source Text':
            b=bytearray(base64.b64decode(p.findtext('value'))); i=b.find(b'@aeconner')
            assert struct.unpack('<I',b[i-4:i])[0]==9 and b[i+9:i+12]==b'\x00\x00\x00'
            b[i-4:i]=struct.pack('<I',10); b[i:i+11]=b'@jake_hock\x00'
            p.find('value').text=base64.b64encode(bytes(b)).decode()
items=v12.findall('clipitem'); k=next(n for n,c in enumerate(list(v12)) if c.tag=='clipitem' and int(c.findtext('start'))>ja)
v12.insert(k,g)
s.find('name').text='ShopTalk_10-26-26_R80_REMAKE'
ET.indent(r,space=' ')
with open(OUT,'w',encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'); f.write(ET.tostring(r,encoding='unicode'))
ET.parse(OUT)
print('jake gfx',ja,jb,'audio tracks',len(aud.findall('track')),'wrote',OUT)
