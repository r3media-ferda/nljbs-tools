import json, os, copy, xml.etree.ElementTree as ET
from urllib.parse import quote
H=os.path.expanduser; D=H('~/r77')
FPS=30000/1001
plan=json.load(open(f'{D}/plan.json')); items=plan['items']; NF=plan['NF']
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/release 77/'
FILES={'AVE':'AVE11878.MP4','093A':'093A2068.MP4','C':'C0003.MP4','OBS':'2026-10-05 19-52-42.mp4','BG':'R77_PLATES/R77_backdrop.png','WH':'R77_PLATES/R77_white.png'}
NATIVE={'AVE':(30,'TRUE',43918),'093A':(30,'TRUE',44817),'C':(120,'TRUE',181320),'OBS':(60,'FALSE',89806),'BG':(30,'TRUE',107892),'WH':(30,'TRUE',107892)}
R76=ET.parse(H('~/mnt/VIDEOS FOR TRAINING/ShopTalk_10-05-26_R76_SYNCED.xml')).getroot(); seq76=R76.find('sequence')
# templates
bm_tpl=None; lum={}
CAM76={'AVE':'AVE11877.MP4','093A':'093A2067.MP4','C':'C0001.MP4'}
for c in R76.iter('clipitem'):
    for f in c.findall('filter'):
        eid=f.findtext('effect/effectid')
        if eid=='basic' and bm_tpl is None and f.find(".//parameter[parameterid='leftcrop']") is not None: bm_tpl=f
        if eid=='Lumetri':
            for k,v in CAM76.items():
                if c.findtext('name')==v and k not in lum: lum[k]=f
def bm(g):
    f=copy.deepcopy(bm_tpl)
    for p in f.iter('parameter'):
        pid=p.findtext('parameterid'); v=p.find('value')
        for kf in p.findall('keyframe'): p.remove(kf)
        if pid=='scale': v.text=f"{g['scale']:.4f}"
        elif pid=='rotation': v.text='0'
        elif pid=='center': v.find('horiz').text=f"{g['cx']:.6f}"; v.find('vert').text=f"{g['cy']:.6f}"
        elif pid=='centerOffset': v.find('horiz').text='0'; v.find('vert').text='0'
        elif pid=='leftcrop': v.text=f"{g['l']:.4f}"
        elif pid=='rightcrop': v.text=f"{g['r']:.4f}"
        elif pid=='topcrop': v.text=f"{g['t']:.4f}"
        elif pid=='bottomcrop': v.text=f"{g['b']:.4f}"
    return f
def rate(tb,nt):
    r=ET.Element('rate'); ET.SubElement(r,'timebase').text=str(tb); ET.SubElement(r,'ntsc').text=nt; return r
used=set()
def fileel(k):
    fe=ET.Element('file',id=f'r77-file-{k}')
    if k in used: return fe
    used.add(k); tb,nt,dur=NATIVE[k]
    ET.SubElement(fe,'name').text=os.path.basename(FILES[k])
    ET.SubElement(fe,'pathurl').text='file://'+quote(BASE+FILES[k])
    fe.append(rate(tb,nt)); ET.SubElement(fe,'duration').text=str(dur)
    m=ET.SubElement(fe,'media'); v=ET.SubElement(m,'video'); sc=ET.SubElement(v,'samplecharacteristics')
    ET.SubElement(sc,'width').text='1920'; ET.SubElement(sc,'height').text='1080'
    if k in('AVE','093A','C','OBS'):
        a=ET.SubElement(m,'audio'); sc=ET.SubElement(a,'samplecharacteristics')
        ET.SubElement(sc,'depth').text='16'; ET.SubElement(sc,'samplerate').text='48000'; ET.SubElement(a,'channelcount').text='2'
    return fe
NAMES={'V4':'BACKDROP','V5':'BORDER post','V6':'BORDER cam','V7':'SPLIT CAM','V8':'IG POST','V9':'IG HANDLE'}
cid=[0]
def clip(it,track):
    cid[0]+=1; k=it['src']; L=it['fb']-it['fa']; i0=max(0,int(round(it['ts']*FPS))) if k not in('BG','WH') else 0
    c=ET.Element('clipitem',id=f'r77-{track}-{cid[0]}')
    ET.SubElement(c,'masterclipid').text=f'r77-mc-{k}'
    ET.SubElement(c,'name').text=NAMES.get(track,os.path.basename(FILES[k])) if k!='OBS' or track in NAMES else os.path.basename(FILES[k])
    ET.SubElement(c,'enabled').text='TRUE'; ET.SubElement(c,'duration').text=str(NATIVE[k][2] if k in('BG','WH') else L)
    c.append(rate(30,'TRUE'))
    for t,v in (('start',it['fa']),('end',it['fb']),('in',i0),('out',i0+L)): ET.SubElement(c,t).text=str(v)
    c.append(fileel(k)); c.append(bm(it['geo']))
    if k in lum: c.append(copy.deepcopy(lum[k]))
    return c
xm=ET.Element('xmeml',version='4'); sq=ET.SubElement(xm,'sequence',id='r77-seq')
ET.SubElement(sq,'name').text='ShopTalk_10-05-26_R77_ROUGHCUT'; ET.SubElement(sq,'duration').text=str(NF); sq.append(rate(30,'TRUE'))
tc=ET.SubElement(sq,'timecode'); tc.append(rate(30,'TRUE')); ET.SubElement(tc,'string').text='00:00:00;00'; ET.SubElement(tc,'frame').text='0'; ET.SubElement(tc,'displayformat').text='DF'
media=ET.SubElement(sq,'media'); vid=ET.SubElement(media,'video')
fmt=ET.SubElement(ET.SubElement(vid,'format'),'samplecharacteristics'); fmt.append(rate(30,'TRUE'))
for t,v in (('width','1920'),('height','1080'),('pixelaspectratio','square'),('fielddominance','none')): ET.SubElement(fmt,t).text=v
# intro elements from R76
r76files={f.get('id'):f for f in R76.iter('file') if len(f)}
seen76=set()
def intro_items(kind,idx):
    trs=seq76.findall(f'media/{kind}/track')
    if idx>=len(trs): return []
    out=[]
    for c in trs[idx]:
        if c.tag not in('clipitem','transitionitem','generatoritem'): continue
        s=int(c.findtext('start')); e=int(c.findtext('end'))
        if not (s<400 and (e<=400 or s<0)): continue
        cc=copy.deepcopy(c)
        if cc.get('id'): cc.set('id','r76intro-'+cc.get('id'))
        for l in cc.findall('link'): cc.remove(l)
        fe=cc.find('file')
        if fe is not None:
            fid=fe.get('id')
            if fid in seen76: 
                for ch in list(fe): fe.remove(ch)
            else:
                seen76.add(fid)
                if len(fe)==0 and fid in r76files:
                    cc.remove(fe); cc.insert(list(cc).index(cc.find('out'))+1 if cc.find('out') is not None else 0, copy.deepcopy(r76files[fid]))
        out.append((s if s>=0 else -1,cc))
    return out
for ti in range(9):
    tr=ET.SubElement(vid,'track')
    els=intro_items('video',ti)
    for s,cc in els: tr.append(cc)
    for it in items[f'V{ti+1}']: tr.append(clip(it,f'V{ti+1}'))
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
aud=ET.SubElement(media,'audio'); ET.SubElement(aud,'numOutputChannels').text='2'
af=ET.SubElement(ET.SubElement(aud,'format'),'samplecharacteristics'); ET.SubElement(af,'depth').text='16'; ET.SubElement(af,'samplerate').text='48000'
T0=82.0
for ti in range(4):
    tr=ET.SubElement(aud,'track')
    for s,cc in intro_items('audio',ti): tr.append(cc)
    if ti<2:
        L=NF-400; i0=int(round(T0*FPS))
        c=ET.SubElement(tr,'clipitem',id=f'r77-dlg-{ti+1}')
        ET.SubElement(c,'masterclipid').text='r77-mc-OBS'; ET.SubElement(c,'name').text='SCREEN REC dialogue '+('L' if ti==0 else 'R')
        ET.SubElement(c,'enabled').text='TRUE'; ET.SubElement(c,'duration').text=str(L); c.append(rate(30,'TRUE'))
        for t,v in (('start',400),('end',NF),('in',i0),('out',i0+L)): ET.SubElement(c,t).text=str(v)
        c.append(fileel('OBS'))
        stv=ET.SubElement(c,'sourcetrack'); ET.SubElement(stv,'mediatype').text='audio'; ET.SubElement(stv,'trackindex').text=str(ti+1)
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
ET.indent(xm,space=' ')
out=H('~/mnt/release 77/ShopTalk_10-05-26_R77_ROUGHCUT.xml')
with open(out,'w',encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'); f.write(ET.tostring(xm,encoding='unicode'))
ET.parse(out)
print('wrote',out,os.path.getsize(out)//1024,'KB; lumetri for',list(lum),'; intro files',len(seen76))
for k in items: print(k,len(items[k]))
