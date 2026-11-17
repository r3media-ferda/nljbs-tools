import os
from urllib.parse import quote
FPS=30000/1001
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 1/'
def fr(t): return int(round(t*FPS))
MIC0=fr(1.505)          # mics start 1.505 s after OBS
# offsets: video start relative to mic start (s); fine xcorr, drift <=10 ms
src={
 'AVE':  dict(f='AVE14201.MP4', tb=30, ntsc='TRUE', vd=1799.063933, nf=53918, o=8.233, ch=2),
 '093A': dict(f='093A6723.MP4', tb=30, ntsc='TRUE', vd=1480.312167, nf=44365, o=4.234, ch=2),
 'C0011':dict(f='C0011.MP4',    tb=120,ntsc='TRUE', vd=1790.2885,   nf=214620, o=15.522, ch=2),
 'OBS':  dict(f='2026-10-26 17-57-32.mp4', tb=60, ntsc='FALSE', vd=2164.566667, nf=129874, o=-1.505, ch=2),
}
mics={'MIC1':dict(f='MIC 1 P.wav',lab='MIC 1 P (Porter)'),'MIC2':dict(f='MIC 2 - AC.wav',lab='MIC 2 AC (Andrew)')}
MICDUR=2013.631474; MICLEN=int(MICDUR*FPS)
for k,s in src.items():
    s['start']=MIC0+fr(s['o']) if k!='OBS' else 0
    s['len']=int(s['vd']*FPS)
    s['err_ms']=((s['start']-MIC0)/FPS-s['o'])*1000
SEQLEN=max([s['start']+s['len'] for s in src.values()]+[MIC0+MICLEN])
R='<rate><timebase>30</timebase><ntsc>TRUE</ntsc></rate>'
used=set()
def fvid(k):
    s=src[k]
    if k in used: return f'<file id="file-{k}"/>'
    used.add(k)
    return f'<file id="file-{k}"><name>{s["f"]}</name><pathurl>file://{quote(BASE+s["f"])}</pathurl><rate><timebase>{s["tb"]}</timebase><ntsc>{s["ntsc"]}</ntsc></rate><duration>{s["nf"]}</duration><media><video><samplecharacteristics><width>1920</width><height>1080</height></samplecharacteristics></video><audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics><channelcount>2</channelcount></audio></media></file>'
def fmic(k):
    m=mics[k]
    if k in used: return f'<file id="file-{k}"/>'
    used.add(k)
    return f'<file id="file-{k}"><name>{m["f"]}</name><pathurl>file://{quote(BASE+m["f"])}</pathurl>{R}<duration>{MICLEN}</duration><media><audio><samplecharacteristics><depth>16</depth><samplerate>44100</samplerate></samplecharacteristics><channelcount>2</channelcount></audio></media></file>'
vorder=['AVE','093A','C0011','OBS']; vtr={k:i+1 for i,k in enumerate(vorder)}
atr={'AVE':3,'093A':4,'C0011':5,'OBS':6}
def links(k):
    return (f'<link><linkclipref>{k}-v</linkclipref><mediatype>video</mediatype><trackindex>{vtr[k]}</trackindex><clipindex>1</clipindex></link>'
            f'<link><linkclipref>{k}-a1</linkclipref><mediatype>audio</mediatype><trackindex>{atr[k]}</trackindex><clipindex>1</clipindex><groupindex>1</groupindex></link>')
def clip(k,kind):
    s=src[k]; L=s['len']; en='TRUE' if kind=='v' else 'FALSE'
    extra='' if kind=='v' else '<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>'
    return f'<clipitem id="{k}-{kind}"><masterclipid>mc-{k}</masterclipid><name>{s["f"]}</name><enabled>{en}</enabled><duration>{L}</duration>{R}<start>{s["start"]}</start><end>{s["start"]+L}</end><in>0</in><out>{L}</out>{fvid(k)}{extra}{links(k)}</clipitem>'
def micclip(k):
    m=mics[k]
    return f'<clipitem id="{k}"><masterclipid>mc-{k}</masterclipid><name>{m["lab"]}</name><enabled>TRUE</enabled><duration>{MICLEN}</duration>{R}<start>{MIC0}</start><end>{MIC0+MICLEN}</end><in>0</in><out>{MICLEN}</out>{fmic(k)}<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>'
T='<enabled>TRUE</enabled><locked>FALSE</locked>'
vt=''.join(f'<track>{clip(k,"v")}{T}</track>' for k in vorder)
at=''.join(f'<track>{micclip(k)}{T}</track>' for k in ['MIC1','MIC2'])
at+=''.join(f'<track>{clip(k,"a1")}<enabled>FALSE</enabled><locked>FALSE</locked></track>' for k in vorder)
name='ShopTalk_10-26-26_R79_SYNCED'
xml=f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4"><sequence id="seq-r79"><name>{name}</name><duration>{SEQLEN}</duration>{R}<timecode>{R}<string>00:00:00;00</string><frame>0</frame><displayformat>DF</displayformat></timecode><media><video><format><samplecharacteristics>{R}<width>1920</width><height>1080</height><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>{vt}</video><audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>{at}</audio></media></sequence></xmeml>
'''
out=os.path.expanduser(f'~/mnt/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 1/{name}.xml')
open(out,'w').write(xml)
import xml.dom.minidom as mm; mm.parseString(xml)
print('mics frame',MIC0)
for k in vorder: s=src[k]; print(k,'V%d'%vtr[k],'o %.3f'%s['o'],'frame',s['start'],'err %.1fms'%s['err_ms'],'end',s['start']+s['len'])
print('SEQ',SEQLEN,round(SEQLEN/FPS,1)); print(out)
