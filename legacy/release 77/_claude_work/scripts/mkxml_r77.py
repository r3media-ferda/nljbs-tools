import json, os
from urllib.parse import quote
D=os.path.expanduser('~/r77'); off=json.load(open(f'{D}/offsets.json'))
FPS=30000/1001
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/release 77/'
def fr(t): return int(round(t*FPS))
# name, key, native timebase, ntsc, vdur_s, adur_s, offset_s
src={
 'AVE':  dict(f='AVE11878.MP4', tb=30, ntsc='TRUE', vd=1465.397267, ad=1465.386667, nf=43918, o=off['camAVE']['fine']),
 '093A': dict(f='093A2068.MP4', tb=30, ntsc='TRUE', vd=1495.393900, ad=1495.381333, nf=44817, o=off['cam093A']['fine']),
 'C0003':dict(f='C0003.MP4',    tb=120,ntsc='TRUE', vd=1512.511000, ad=1512.515000, nf=181320, o=off['camC0003']['fine']),
 'OBS':  dict(f='2026-10-05 19-52-42.mp4', tb=60, ntsc='FALSE', vd=1496.766667, ad=1496.746667, nf=89806, o=0.0),
}
for k,s in src.items():
    s['start']=fr(s['o']); s['vlen']=int(s['vd']*FPS); s['alen']=int(s['ad']*FPS)
    s['err_ms']=(s['start']/FPS-s['o'])*1000
SEQLEN=max(s['start']+max(s['vlen'],s['alen']) for s in src.values())
R='<rate><timebase>30</timebase><ntsc>TRUE</ntsc></rate>'
def filedef(k):
    s=src[k]
    return f'''<file id="file-{k}"><name>{s['f']}</name><pathurl>file://{quote(BASE+s['f'])}</pathurl><rate><timebase>{s['tb']}</timebase><ntsc>{s['ntsc']}</ntsc></rate><duration>{s['nf']}</duration><media><video><samplecharacteristics><width>1920</width><height>1080</height></samplecharacteristics></video><audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics><channelcount>2</channelcount></audio></media></file>'''
used=set()
def fref(k):
    if k in used: return f'<file id="file-{k}"/>'
    used.add(k); return filedef(k)
def links(k,chs):
    out=f'<link><linkclipref>{k}-v</linkclipref><mediatype>video</mediatype><trackindex>{vtrack[k]}</trackindex><clipindex>1</clipindex></link>'
    for ch,t in chs: out+=f'<link><linkclipref>{k}-a{ch}</linkclipref><mediatype>audio</mediatype><trackindex>{t}</trackindex><clipindex>1</clipindex><groupindex>1</groupindex></link>'
    return out
vorder=['AVE','093A','C0003','OBS']; vtrack={k:i+1 for i,k in enumerate(vorder)}
# audio: A1/A2 = screen-rec L/R (dialogue bed); A3-A5 = cam scratch ch1 (disabled)
achs={'OBS':[(1,1),(2,2)],'AVE':[(1,3)],'093A':[(1,4)],'C0003':[(1,5)]}
def vclip(k):
    s=src[k]; L=s['vlen']
    return f'''<clipitem id="{k}-v"><masterclipid>mc-{k}</masterclipid><name>{s['f']}</name><enabled>TRUE</enabled><duration>{L}</duration>{R}<start>{s['start']}</start><end>{s['start']+L}</end><in>0</in><out>{L}</out>{fref(k)}{links(k,achs[k])}</clipitem>'''
def aclip(k,ch,enabled):
    s=src[k]; L=s['alen']
    return f'''<clipitem id="{k}-a{ch}"><masterclipid>mc-{k}</masterclipid><name>{s['f']}</name><enabled>{enabled}</enabled><duration>{L}</duration>{R}<start>{s['start']}</start><end>{s['start']+L}</end><in>0</in><out>{L}</out>{fref(k)}<sourcetrack><mediatype>audio</mediatype><trackindex>{ch}</trackindex></sourcetrack>{links(k,achs[k])}</clipitem>'''
vt=''.join(f'<track>{vclip(k)}<enabled>TRUE</enabled><locked>FALSE</locked></track>' for k in vorder)
at=''
for k in ['OBS']:
    for ch,t in achs[k]: at+=f'<track>{aclip(k,ch,"TRUE")}<enabled>TRUE</enabled><locked>FALSE</locked><outputchannelindex>{ch}</outputchannelindex></track>'
for k in ['AVE','093A','C0003']:
    for ch,t in achs[k]: at+=f'<track>{aclip(k,ch,"FALSE")}<enabled>FALSE</enabled><locked>FALSE</locked></track>'
xml=f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4"><sequence id="seq-r77"><name>ShopTalk_10-05-26_R77_SYNCED</name><duration>{SEQLEN}</duration>{R}<timecode>{R}<string>00:00:00;00</string><frame>0</frame><displayformat>DF</displayformat></timecode><media><video><format><samplecharacteristics>{R}<width>1920</width><height>1080</height><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>{vt}</video><audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>{at}</audio></media></sequence></xmeml>
'''
out=os.path.expanduser('~/mnt/release 77/ShopTalk_10-05-26_R77_SYNCED.xml')
open(out,'w').write(xml)
import xml.dom.minidom as m; m.parseString(xml)
for k in vorder: s=src[k]; print(k,'V%d'%vtrack[k],'offset %.3f'%s['o'],'frame',s['start'],'err %.1fms'%s['err_ms'],'end',s['start']+s['vlen'])
print('SEQ',SEQLEN,'frames',round(SEQLEN/FPS,1),'s'); print(out)
