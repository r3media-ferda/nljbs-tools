import os
from urllib.parse import quote
FPS=30000/1001
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 2/'
MICDIR=BASE+'NUMBER 2.band/Media/Audio Files/'
def fr(t): return int(round(t*FPS))
# video start relative to mic start (s), mid-run fine xcorr (0.5 ms hop); drift head->tail <= 9 ms
src={
 'AVE':  dict(f='AVE14202.MP4', tb=30, ntsc='TRUE', vd=1641.306333, fps=FPS,      o=-40.9585),
 '093A': dict(f='093A6724.MP4', tb=30, ntsc='TRUE', vd=1659.691367, fps=FPS,      o=-61.856),
 'C0012':dict(f='C0012.MP4',    tb=120,ntsc='TRUE', vd=1690.19,     fps=4*FPS,    o=-81.128),
 'OBS':  dict(f='2026-10-26 18-33-39.mp4', tb=60, ntsc='FALSE', vd=1810.818, fps=60, o=-64.4875),
}
mics={'MIC1':'Mic 1 #54.wav','MIC2':'Mic 2 #54.wav','MIC3':'Mic 3 #53.wav'}
MICDUR=1732.0; MICLEN=int(MICDUR*FPS)
MIC0=fr(81.128)   # C0012 rolled first -> at 0
for k,s in src.items():
    s['nf']=int(round(s['vd']*s['fps']))
    s['start']=MIC0+fr(s['o']) if k!='C0012' else 0
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
    f=mics[k]
    if k in used: return f'<file id="file-{k}"/>'
    used.add(k)
    return f'<file id="file-{k}"><name>{f}</name><pathurl>file://{quote(MICDIR+f)}</pathurl>{R}<duration>{MICLEN}</duration><media><audio><samplecharacteristics><depth>24</depth><samplerate>44100</samplerate></samplecharacteristics><channelcount>1</channelcount></audio></media></file>'
vorder=['AVE','093A','C0012','OBS']; vtr={k:i+1 for i,k in enumerate(vorder)}
atr={k:i+4 for i,k in enumerate(vorder)}
def links(k):
    return (f'<link><linkclipref>{k}-v</linkclipref><mediatype>video</mediatype><trackindex>{vtr[k]}</trackindex><clipindex>1</clipindex></link>'
            f'<link><linkclipref>{k}-a1</linkclipref><mediatype>audio</mediatype><trackindex>{atr[k]}</trackindex><clipindex>1</clipindex><groupindex>1</groupindex></link>')
def clip(k,kind):
    s=src[k]; L=s['len']; en='TRUE' if kind=='v' else 'FALSE'
    extra='' if kind=='v' else '<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>'
    return f'<clipitem id="{k}-{kind}"><masterclipid>mc-{k}</masterclipid><name>{s["f"]}</name><enabled>{en}</enabled><duration>{L}</duration>{R}<start>{s["start"]}</start><end>{s["start"]+L}</end><in>0</in><out>{L}</out>{fvid(k)}{extra}{links(k)}</clipitem>'
def micclip(k):
    return f'<clipitem id="{k}"><masterclipid>mc-{k}</masterclipid><name>{mics[k]}</name><enabled>TRUE</enabled><duration>{MICLEN}</duration>{R}<start>{MIC0}</start><end>{MIC0+MICLEN}</end><in>0</in><out>{MICLEN}</out>{fmic(k)}<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>'
T='<enabled>TRUE</enabled><locked>FALSE</locked>'
vt=''.join(f'<track>{clip(k,"v")}{T}</track>' for k in vorder)
at=''.join(f'<track>{micclip(k)}{T}</track>' for k in mics)
at+=''.join(f'<track>{clip(k,"a1")}<enabled>FALSE</enabled><locked>FALSE</locked></track>' for k in vorder)
name='ShopTalk_10-26-26_R80_SYNCED'
xml=f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4"><sequence id="seq-r80"><name>{name}</name><duration>{SEQLEN}</duration>{R}<timecode>{R}<string>00:00:00;00</string><frame>0</frame><displayformat>DF</displayformat></timecode><media><video><format><samplecharacteristics>{R}<width>1920</width><height>1080</height><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>{vt}</video><audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>{at}</audio></media></sequence></xmeml>
'''
open(f'{name}.xml','w').write(xml)
import xml.dom.minidom as mm; mm.parseString(xml)
print('mics frame',MIC0)
for k in vorder: s=src[k]; print(k,'V%d'%vtr[k],'o %.4f'%s['o'],'frame',s['start'],'err %.1fms'%s['err_ms'],'end',s['start']+s['len'])
print('SEQ',SEQLEN,round(SEQLEN/FPS,1))
