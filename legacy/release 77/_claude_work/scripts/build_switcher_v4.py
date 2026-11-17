import json, os, copy, xml.etree.ElementTree as ET
from urllib.parse import quote
H=os.path.expanduser; D=H('~/r77')
FPS=30000/1001; T0=82.0; INTRO=400
plan=json.load(open(f'{D}/plan.json')); NF=plan['NF']; NB=NF-INTRO
STATES=[s for s in json.load(open(f'{D}/states_h.json'))['states']]
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/release 77/'
OFF={'AVE':81.611,'093A':56.070,'C':36.331,'OBS':0.0}
FILES={'AVE':'AVE11878.MP4','093A':'093A2068.MP4','C':'C0003.MP4','OBS':'2026-10-05 19-52-42.mp4','BG':'R77_PLATES/R77_backdrop.png','WH':'R77_PLATES/R77_white.png'}
NATIVE={'AVE':(30,'TRUE',43918),'093A':(30,'TRUE',44817),'C':(120,'TRUE',181320),'OBS':(60,'FALSE',89806),'BG':(30,'TRUE',107892),'WH':(30,'TRUE',107892)}
R76=ET.parse(H('~/mnt/VIDEOS FOR TRAINING/ShopTalk_10-05-26_R76_SYNCED.xml')).getroot(); seq76=R76.find('sequence')
bm_tpl=next(f for c in R76.iter('clipitem') for f in c.findall('filter') if f.findtext('effect/effectid')=='basic' and f.find(".//parameter[parameterid='leftcrop']") is not None)
def G(t): return int(round((t-T0)*FPS))   # angle-sequence frame
# ---------- geometry (same as rough cut) ----------
SUBJ={'AVE':(960,900),'093A':(1090,1400),'C':(960,1700)}
BW=6
def place(src,out,scale):
    sx0,sy0,sx1,sy1=src; ox0,oy0=out; s=scale/100
    PX=ox0-(sx0-960)*s; PY=oy0-(sy0-540)*s
    return dict(scale=scale,cx=(PX-960)/1920,cy=(PY-540)/1080,l=sx0/19.2,r=(1920-sx1)/19.2,t=sy0/10.8,b=(1080-sy1)/10.8)
def full(sc): return dict(scale=sc,cx=0,cy=0,l=0,r=0,t=0,b=0)
def white(r):
    x0,y0,x1,y1=r; x0=max(0,x0-BW); y0=max(0,y0-BW); x1=min(1920,x1+BW); y1=min(1080,y1+BW)
    return dict(scale=100,cx=0,cy=0,l=x0/19.2,r=(1920-x1)/19.2,t=y0/10.8,b=(1080-y1)/10.8)
def camfit(cam,bx0,by0,bw,bh):
    cx,mw=SUBJ[cam]; sw=min(1920,max(mw,1080*bw/bh)); sh=min(1080,sw*bh/bw)
    sx0=min(max(0,cx-sw/2),1920-sw); sy0=(1080-sh)*0.35; sc=bw/sw*100; dh=sh*sc/100
    out=(bx0,by0+(bh-dh)/2); return place((sx0,sy0,sx0+sw,sy0+sh),out,sc),(out[0],out[1],out[0]+bw,out[1]+dh)
def media_src(st,maxar):
    x0,x1,y0,y1=st['box']; w=x1-x0; hh=y1-y0
    if w/hh>maxar: c=(x0+x1)/2; w=hh*maxar; x0=c-w/2; x1=c+w/2
    return (x0,y0,x1,y1)
def layout(mode,st,cam):
    """returns list of (track,src,geo,is_source_timed)"""
    L=[(1,'BG',full(100),False)]
    if mode=='A':
        src=media_src(st,1.0); ar=(src[2]-src[0])/(src[3]-src[1]); PH=900; PW=PH*ar; px0=1880-PW
        L+= [(2,'WH',white((px0,150,1880,1050)),False),(5,'OBS',place(src,(px0,150),PH/(src[3]-src[1])*100),True)]
        g,cr=camfit(cam,40,150,px0-70,900); L+=[(3,'WH',white(cr),False),(4,cam,g,True)]
        if st['hdr']:
            hx0,hx1,hy0,hy1=st['hdr']
            if st['kind']=='reel': L.append((6,'OBS',place((hx0,hy0,hx1,hy1),(px0-30-(hx1-hx0)*1.15,1050-(hy1-hy0)*1.15),115),True))
            else: L.append((6,'OBS',place((hx0,hy0,hx1,hy1),(1880-(hx1-hx0)*1.6,40),160),True))
    else:  # 'B' with pip cam, or 'T' tattoo only
        src=media_src(st,1.84); ar=(src[2]-src[0])/(src[3]-src[1]); PH=1000; PW=PH*ar
        if PW>1840: PW=1840; PH=PW/ar
        px0=(1920-PW)/2; py0=(1080-PH)/2
        L+= [(2,'WH',white((px0,py0,px0+PW,py0+PH)),False),(5,'OBS',place(src,(px0,py0),PH/(src[3]-src[1])*100),True)]
        if mode=='B':
            pr=(40,788,488,1040); L+=[(3,'WH',white(pr),False),(4,cam,place((0,0,1920,1080),(40,788),448/19.2),True)]
        if st['hdr']:
            hx0,hx1,hy0,hy1=st['hdr']
            if st['kind']=='reel': L.append((6,'OBS',place((hx0,hy0,hx1,hy1),(max(20,px0-30-(hx1-hx0)*1.5),40),150),True))
            else: L.append((6,'OBS',place((hx0,hy0,hx1,hy1),(px0+20,py0+20),135),True))
    return L
# usable state windows
WIN=[]
for st in STATES:
    a,b=max(st['t0'],T0),plan and min(st['t1'],T0+NB/FPS)
    if b-a>=2.5: WIN.append((G(a),G(b),st))
ANGLES=[ # (name, kind, cam, fallback cam, fallback scale)
 ('1 NICK','full','AVE',None,107),('2 ANDREW + PORTER','full','093A',None,111),('3 WIDE','full','C',None,100),
 ('4 SPLIT - NICK + TATTOO','A','AVE','AVE',107),('5 SPLIT - GUESTS + TATTOO','A','093A','093A',111),
 ('6 TATTOO + NICK PIP','B','AVE','AVE',107),('7 TATTOO + GUESTS PIP','B','093A','093A',111),
 ('8 TATTOO ONLY','T',None,'C',100),('9 NICK TIGHT','full','AVE',None,122),('10 GUESTS TIGHT','full','093A',None,124)]
# ---------- XML helpers ----------
def rate(tb=30,nt='TRUE'):
    r=ET.Element('rate'); ET.SubElement(r,'timebase').text=str(tb); ET.SubElement(r,'ntsc').text=nt; return r
used=set()
def fileel(k):
    fe=ET.Element('file',id=f'r77-file-{k}')
    if k in used: return fe
    used.add(k); tb,nt,dur=NATIVE[k]
    ET.SubElement(fe,'name').text=os.path.basename(FILES[k]); ET.SubElement(fe,'pathurl').text='file://'+quote(BASE+FILES[k])
    fe.append(rate(tb,nt)); ET.SubElement(fe,'duration').text=str(dur)
    m=ET.SubElement(fe,'media'); v=ET.SubElement(m,'video'); sc=ET.SubElement(v,'samplecharacteristics')
    ET.SubElement(sc,'width').text='1920'; ET.SubElement(sc,'height').text='1080'
    if k in('AVE','093A','C','OBS'):
        a=ET.SubElement(m,'audio'); sc=ET.SubElement(a,'samplecharacteristics'); ET.SubElement(sc,'depth').text='16'; ET.SubElement(sc,'samplerate').text='48000'; ET.SubElement(a,'channelcount').text='2'
    return fe
def bm(g):
    f=copy.deepcopy(bm_tpl)
    for p in f.iter('parameter'):
        pid=p.findtext('parameterid'); v=p.find('value')
        for kf in p.findall('keyframe'): p.remove(kf)
        if pid=='scale': v.text=f"{g['scale']:.4f}"
        elif pid=='rotation': v.text='0'
        elif pid=='center': v.find('horiz').text=f"{g['cx']:.6f}"; v.find('vert').text=f"{g['cy']:.6f}"
        elif pid=='centerOffset': v.find('horiz').text='0'; v.find('vert').text='0'
        elif pid in('leftcrop','rightcrop','topcrop','bottomcrop'): v.text=f"{g[pid[0]]:.4f}"
    return f
cid=[0]
TRN={1:'BACKDROP',2:'BORDER post',3:'BORDER cam',5:'IG POST',6:'IG HANDLE'}
def clip(k,start,end,geo,timed,name=None,enabled=True):
    cid[0]+=1; L=end-start
    i0=int(round((T0-OFF[k])*FPS))+start if timed else 0
    c=ET.Element('clipitem',id=f'r77c-{cid[0]}')
    ET.SubElement(c,'masterclipid').text=f'r77-mc-{k}'; ET.SubElement(c,'name').text=name or os.path.basename(FILES[k])
    ET.SubElement(c,'enabled').text='TRUE' if enabled else 'FALSE'
    ET.SubElement(c,'duration').text=str(NATIVE[k][2] if k in('BG','WH') else L); c.append(rate())
    for t,v in (('start',start),('end',end),('in',i0),('out',i0+L)): ET.SubElement(c,t).text=str(v)
    c.append(fileel(k)); c.append(bm(geo)); return c
def seq_shell(sid,name,dur):
    s=ET.Element('sequence',id=sid); ET.SubElement(s,'name').text=name; ET.SubElement(s,'duration').text=str(dur); s.append(rate())
    tc=ET.SubElement(s,'timecode'); tc.append(rate()); ET.SubElement(tc,'string').text='00:00:00;00'; ET.SubElement(tc,'frame').text='0'; ET.SubElement(tc,'displayformat').text='DF'
    media=ET.SubElement(s,'media'); vid=ET.SubElement(media,'video')
    fmt=ET.SubElement(ET.SubElement(vid,'format'),'samplecharacteristics'); fmt.append(rate())
    for t,v in (('width','1920'),('height','1080'),('pixelaspectratio','square'),('fielddominance','none')): ET.SubElement(fmt,t).text=v
    return s,media,vid
def build_angle(i,a):
    name,kind,cam,fb,sc=a
    s,media,vid=seq_shell(f'r77-ang-{i}',f'R77 ANG {name}',NB)
    tracks={t:ET.SubElement(vid,'track') for t in range(1,7 if kind!='full' else 2)}
    if kind=='full':
        tracks[1].append(clip(cam,0,NB,full(sc),True))
    else:
        t=0
        for g0,g1,st in WIN+[(NB,NB,None)]:
            if g0>t: tracks[1].append(clip(fb,t,g0,full(sc),True))
            if st is None: break
            mode={'A':'A','B':'B','T':'T'}[kind]
            if kind=='A' and (st['kind']=='zoom' or (st['box'][1]-st['box'][0])/(st['box'][3]-st['box'][2])>1.15): mode='A'
            for tr,k,geo,timed in layout(mode,st,cam):
                tracks[tr].append(clip(k,g0,g1,geo,timed,name=TRN.get(tr,'SPLIT CAM' if tr==4 else None)))
            t=g1
    for tr in tracks.values(): ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
    return s
angle_seqs=[]  # built lazily on first reference
def nest(i,start,end,inp,enabled,name):
    cid[0]+=1; L=end-start
    c=ET.Element('clipitem',id=f'r77n-{cid[0]}')
    ET.SubElement(c,'masterclipid').text=f'r77-mc-ang-{i}'; ET.SubElement(c,'name').text=name
    ET.SubElement(c,'enabled').text='TRUE' if enabled else 'FALSE'; ET.SubElement(c,'duration').text=str(NB if i>0 else L); c.append(rate())
    for t,v in (('start',start),('end',end),('in',inp),('out',inp+L)): ET.SubElement(c,t).text=str(v)
    return c
defined=set()
def nest_angle(i,start,end,inp,enabled):
    c=nest(i,start,end,inp,enabled,'ANG '+ANGLES[i][0])
    if i in defined: ET.SubElement(c,'sequence',id=f'r77-ang-{i}')
    else: defined.add(i); c.append(build_angle(i,ANGLES[i]))
    return c
# ---------- main switcher sequence ----------
def pick(s):
    if s['mode']=='F': return {'AVE':8 if s['punch'] else 0,'093A':9 if s['punch'] else 1,'C':2}[s['cam']]
    if s['mode']=='A': return 3 if s['cam']=='AVE' else 4
    if s['mode']=='T': return 7
    return 5 if s['cam']=='AVE' else 6
main,media,vid=seq_shell('r77-main','ShopTalk_10-05-26_R77_SWITCHER_v4',NF)
r76files={f.get('id'):f for f in R76.iter('file') if len(f)}; seen76=set()
def intro_items(kind,idx):
    trs=seq76.findall(f'media/{kind}/track'); out=[]
    if idx>=len(trs): return out
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
                    idx2=list(cc).index(fe); cc.remove(fe); cc.insert(idx2,copy.deepcopy(r76files[fid]))
        out.append(cc)
    return out
segs=plan['segs']
import numpy as _np
_E=_np.load(f'{D}/user_edits.npz'); _v3=_E['v3']; _user=_E['user']; _rem=_E['removed']; _chg=_E['changed']
_final=_v3.copy()
_i=0
while _i<len(_chg):
    if _chg[_i]:
        _j=_i
        while _j<len(_chg) and _chg[_j]: _j+=1
        if _j-_i>=3: _final[_i:_j]=_user[_i:_j]
        _i=_j
    else: _i+=1
_segid=_np.zeros(NB,int)
for _k,_s in enumerate(segs): _segid[_s['fa']-INTRO:_s['fb']-INTRO]=_k
FINAL=[]; KEPT=[]; _t=INTRO; _g=0
while _g<NB:
    if _rem[_g]: _g+=1; continue
    _h=_g
    while _h<NB and not _rem[_h] and _final[_h]==_final[_g] and _segid[_h]==_segid[_g]: _h+=1
    FINAL.append(dict(start=_t,end=_t+(_h-_g),inp=_g,ang=int(_final[_g])))
    if KEPT and KEPT[-1][1]==_g: KEPT[-1]=(KEPT[-1][0],_h,KEPT[-1][2])
    else: KEPT.append((_g,_h,_t))
    _t+=_h-_g; _g=_h
NF=_t
for ti in range(10):
    tr=ET.SubElement(vid,'track')
    for cc in intro_items('video',ti): tr.append(cc)
    for s in FINAL:
        tr.append(nest_angle(ti,s['start'],s['end'],s['inp'],s['ang']==ti))
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
# V11: the ANGLES stack (for multicam), disabled
tr=ET.SubElement(vid,'track')
stack,smedia,svid=seq_shell('r77-stack','R77 ANGLES - MULTICAM SOURCE',NB)
for i in range(10):
    t2=ET.SubElement(svid,'track'); t2.append(nest_angle(i,0,NB,0,True)); ET.SubElement(t2,'enabled').text='TRUE'; ET.SubElement(t2,'locked').text='FALSE'
for _n,(_a,_b,_ts) in enumerate(KEPT):
    c=nest(-1,_ts,_ts+(_b-_a),_a,False,'R77 ANGLES - MULTICAM SOURCE')
    if _n==0: c.append(stack)
    else: ET.SubElement(c,'sequence',id='r77-stack')
    tr.append(c)
ET.SubElement(tr,'enabled').text='FALSE'; ET.SubElement(tr,'locked').text='FALSE'
# audio
aud=ET.SubElement(media,'audio'); ET.SubElement(aud,'numOutputChannels').text='2'
af=ET.SubElement(ET.SubElement(aud,'format'),'samplecharacteristics'); ET.SubElement(af,'depth').text='16'; ET.SubElement(af,'samplerate').text='48000'
for ti in range(4):
    tr=ET.SubElement(aud,'track')
    for cc in intro_items('audio',ti): tr.append(cc)
    if ti<2:
      for _n,(_a,_b,_ts) in enumerate(KEPT):
        L=_b-_a; i0=int(round(T0*FPS))+_a
        c=ET.SubElement(tr,'clipitem',id=f'r77-dlg-{ti+1}-{_n}'); ET.SubElement(c,'masterclipid').text='r77-mc-OBS'
        ET.SubElement(c,'name').text='SCREEN REC dialogue '+('L' if ti==0 else 'R'); ET.SubElement(c,'enabled').text='TRUE'
        ET.SubElement(c,'duration').text=str(L); c.append(rate())
        for t,v in (('start',_ts),('end',_ts+L),('in',i0),('out',i0+L)): ET.SubElement(c,t).text=str(v)
        c.append(fileel('OBS')); st_=ET.SubElement(c,'sourcetrack'); ET.SubElement(st_,'mediatype').text='audio'; ET.SubElement(st_,'trackindex').text=str(ti+1)
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
main.find('duration').text=str(NF)
xm=ET.Element('xmeml',version='4'); xm.append(main)
ET.indent(xm,space=' ')
out=H('~/mnt/release 77/ShopTalk_10-05-26_R77_SWITCHER_v4.xml')
with open(out,'w',encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'); f.write(ET.tostring(xm,encoding='unicode'))
ET.parse(out)
from collections import Counter
print('wrote',os.path.getsize(out)//1024,'KB; cuts',len(FINAL),'NF',NF,'kept ranges',len(KEPT),'angle use',Counter(ANGLES[f['ang']][0] for f in FINAL))
print('state windows',len(WIN),'lumetri: none')
