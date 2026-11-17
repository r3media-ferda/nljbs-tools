import json, os, copy, sys, numpy as np, xml.etree.ElementTree as ET
from urllib.parse import quote
from collections import Counter
H=os.path.expanduser
os.chdir(H('~/r78'))
FPS=30000/1001; INTRO=400
P=json.load(open('plan_base.json')); B0,B1=P['B0'],P['B1']; OFF=P['OFF']; SECT=P['SECT']
NB=int(round((B1-B0)*FPS))
def G(m): return int(round((m-B0)*FPS))
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/10.05.26/Release 78/'
FILES={'AVE':'AVE11879.MP4','093A':'093A2069.MP4','C':'C0004.MP4','OBS':'2026-10-05 20-27-08.mp4',
 'M1':'Mic 1#53.wav','M2':'Mic 2#53.wav','M3':'Mic 3#54.wav',
 'BG':'R78_PLATES/R78_backdrop.png','WH':'R78_PLATES/R78_white.png','BK':'R78_PLATES/R78_black.png',
 'CARD_tiger_ramos':'R78_PLATES/card_tiger_ramos.png','CARD_chadchesko':'R78_PLATES/card_chadchesko.png','CARD_stewart_modernclassic':'R78_PLATES/card_stewart_modernclassic.png'}
NATIVE={'AVE':(30,'TRUE',39976),'093A':(30,'TRUE',40978),'C':(120,'TRUE',158580),'OBS':(60,'FALSE',78161),
 'M1':(30,'TRUE',39200),'M2':(30,'TRUE',39200),'M3':(30,'TRUE',39200)}
for h in P['holds']: FILES['H_'+h['f']]='R78_PLATES/holds/'+h['f']
def STILL(k): return k in('BG','WH','BK') or k.startswith('CARD_') or k.startswith('H_')
for k in FILES:
    if STILL(k): NATIVE[k]=(30,'TRUE',107892)
OFF2=dict(OFF); OFF2['M1']=OFF2['M2']=OFF2['M3']=0.0

# ================= EDIT DECISIONS =================
runs=P['runs']
CAM={1:'AVE',2:'093A',3:'093A',4:'C'}
shots=[]
for a,b,s in runs:
    cam=CAM[s]; d=b-a
    if d>12 and cam!='C':
        c0=a+d*0.45; c1=min(b-2.0,c0+3.5)
        shots+=[[a,c0,cam,0],[c0,c1,'C',0],[c1,b,cam,0]]
    else: shots.append([a,b,cam,0])
cnt=Counter()
for s in shots:          # punch-ins: every 5th shot per camera (Avery pulled R77's back)
    if s[2]!='C':
        cnt[s[2]]+=1
        if cnt[s[2]]%5==0 and s[1]-s[0]>4: s[3]=1
# screen-section layout cycle: T tattoo only / A split / F full cam / W wide
PAT=[('T',5),('A',8),('F',4),('A',8),('W',3),('A',7),('F',4),('A',8)]
lay=[]
for S in SECT:
    a=max(S['m0'],B0); b=min(S['m1'],B1); t=a; k=0
    while t<b-0.01:
        m,dd=PAT[k%len(PAT)]; e=min(b,t+dd)
        if b-e<2.5: e=b
        lay.append([t,e,m,S['id']]); t=e; k+=1
for a,b in P['video_sil']:   # silent while a tattoo video plays -> tattoo only
    nl=[]
    for l in lay:
        if l[1]<=a or l[0]>=b: nl.append(l); continue
        if l[0]<a: nl.append([l[0],a,l[2],l[3]])
        nl.append([max(l[0],a),min(l[1],b),'T',l[3]])
        if l[1]>b: nl.append([b,l[1],l[2],l[3]])
    lay=nl
def find(lst,t):
    for e in lst:
        if e[0]<=t<e[1]: return e
    return None
bounds=sorted(set([B0,B1]+[x for s in shots for x in s[:2]]+[x for l in lay for x in l[:2]]))
bounds=[x for x in bounds if B0<=x<=B1]
segs=[]
for a,b in zip(bounds[:-1],bounds[1:]):
    if b-a<1e-6: continue
    mid=(a+b)/2; c=find(shots,mid); l=find(lay,mid)
    mode=l[2] if l else 'F'
    cam,punch=c[2],c[3]
    if mode=='W': mode,cam,punch='F','C',0
    if mode=='A' and cam=='C':
        r=find(runs,mid); cam='AVE' if r and r[2]==1 else '093A'
    if mode=='F': ang={'AVE':8 if punch else 0,'093A':9 if punch else 1,'C':2}[cam]
    elif mode=='A': ang=3 if cam=='AVE' else 4
    else: ang=7
    if segs and segs[-1]['ang']==ang: segs[-1]['b']=b
    else: segs.append(dict(a=a,b=b,ang=ang))
out=[]
for s in segs:
    if out and (s['b']-s['a']<2.0 or out[-1]['ang']==s['ang']): out[-1]['b']=s['b']
    else: out.append(s)
segs=out
ang_g=np.zeros(NB,int); seg_g=np.zeros(NB,int)
for i,s in enumerate(segs):
    ga,gb=G(s['a']),min(NB,G(s['b'])); ang_g[ga:gb]=s['ang']; seg_g[ga:gb]=i
removed=np.zeros(NB,bool)
for a,b in P['cuts']: removed[G(a):G(b)]=True

# ================= GEOMETRY =================
BW=6
def place(src,out,scale):
    sx0,sy0,sx1,sy1=src; ox0,oy0=out; s=scale/100
    PX=ox0-(sx0-960)*s; PY=oy0-(sy0-540)*s
    return dict(scale=scale,cx=(PX-960)/1920,cy=(PY-540)/1080,l=sx0/19.2,r=(1920-sx1)/19.2,t=sy0/10.8,b=(1080-sy1)/10.8)
def full(sc,cx=0.0): return dict(scale=sc,cx=cx,cy=0,l=0,r=0,t=0,b=0)
def plate(r,pad=0):
    x0,y0,x1,y1=r; x0=max(0,x0-pad); y0=max(0,y0-pad); x1=min(1920,x1+pad); y1=min(1080,y1+pad)
    return dict(scale=100,cx=0,cy=0,l=x0/19.2,r=(1920-x1)/19.2,t=y0/10.8,b=(1080-y1)/10.8)
SUBJ={'AVE':(960,900),'093A':(960,1500),'C':(960,1700)}
def camfit(cam,bx0,by0,bw,bh):
    cx,mw=SUBJ[cam]; sw=min(1920,max(mw,1080*bw/bh)); sh=min(1080,sw*bh/bw)
    sx0=min(max(0,cx-sw/2),1920-sw); sy0=(1080-sh)*0.35; sc=bw/sw*100; dh=sh*sc/100
    out=(bx0,by0+(bh-dh)/2); return place((sx0,sy0,sx0+sw,sy0+sh),out,sc),(out[0],out[1],out[0]+bw,out[1]+dh)
def panel(mode,PA):
    # every layout: post panel right-aligned at x1880, directly under the handle card (card y36-163)
    PH=870; PW=PH*PA; return (1880-PW,180,1880,1050)
def fitc(box,PA,pr):
    x0,y0,x1,y1=box; w=x1-x0; h=y1-y0
    if w/h>PA: c=(x0+x1)/2; w=h*PA; x0=c-w/2; x1=c+w/2
    PW=pr[2]-pr[0]; PH=pr[3]-pr[1]; s=min(PW/(x1-x0),PH/(y1-y0))
    ox=pr[0]+(PW-(x1-x0)*s)/2; oy=pr[1]+(PH-(y1-y0)*s)/2
    return place((x0,y0,x1,y1),(ox,oy),s*100)
ANGLES=[('1 NICK','full','AVE',107),('2 ANDREW + PORTER','full','093A',111),('3 WIDE','full','C',100),
 ('4 SPLIT - NICK + TATTOO','A','AVE',107),('5 SPLIT - GUESTS + TATTOO','A','093A',111),
 ('6 TATTOO + NICK PIP','B','AVE',107),('7 TATTOO + GUESTS PIP','B','093A',111),
 ('8 TATTOO ONLY','T','C',100),('9 NICK TIGHT','full','AVE',122),('10 GUESTS TIGHT','full','093A',124)]

# ================= XML HELPERS =================
FIN=ET.parse(H('~/mnt/NLJBS Drive/WORKING SHOP TALM FILES/VIDEOS FOR TRAINING/FINAL EDIT XML.xml')).getroot(); seqF=FIN.find('sequence')
bm_tpl=next(f for c in FIN.iter('clipitem') for f in c.findall('filter') if f.findtext('effect/effectid')=='basic' and f.find(".//parameter[parameterid='leftcrop']") is not None)
def rate(tb=30,nt='TRUE'):
    r=ET.Element('rate'); ET.SubElement(r,'timebase').text=str(tb); ET.SubElement(r,'ntsc').text=nt; return r
def safe(k): return ''.join(ch if ch.isalnum() else '_' for ch in k)
used=set()
def fileel(k):
    fe=ET.Element('file',id='r78-file-'+safe(k))
    if k in used: return fe
    used.add(k); tb,nt,dur=NATIVE[k]
    ET.SubElement(fe,'name').text=os.path.basename(FILES[k]); ET.SubElement(fe,'pathurl').text='file://'+quote(BASE+FILES[k])
    fe.append(rate(tb,nt)); ET.SubElement(fe,'duration').text=str(dur)
    m=ET.SubElement(fe,'media')
    if k not in('M1','M2','M3'):
        v=ET.SubElement(m,'video'); sc=ET.SubElement(v,'samplecharacteristics'); ET.SubElement(sc,'width').text='1920'; ET.SubElement(sc,'height').text='1080'
    if k in('AVE','093A','C','OBS'):
        a=ET.SubElement(m,'audio'); sc=ET.SubElement(a,'samplecharacteristics'); ET.SubElement(sc,'depth').text='16'; ET.SubElement(sc,'samplerate').text='48000'; ET.SubElement(a,'channelcount').text='2'
    if k in('M1','M2','M3'):
        a=ET.SubElement(m,'audio'); sc=ET.SubElement(a,'samplecharacteristics'); ET.SubElement(sc,'depth').text='24'; ET.SubElement(sc,'samplerate').text='44100'; ET.SubElement(a,'channelcount').text='1'
    return fe
def bm(g):
    f=copy.deepcopy(bm_tpl)
    for p in f.iter('parameter'):
        pid=p.findtext('parameterid'); v=p.find('value')
        for kf in p.findall('keyframe'): p.remove(kf)
        if v is None: continue
        if pid=='scale': v.text=f"{g['scale']:.4f}"
        elif pid=='rotation': v.text='0'
        elif pid=='center': v.find('horiz').text=f"{g['cx']:.6f}"; v.find('vert').text=f"{g['cy']:.6f}"
        elif pid=='centerOffset': v.find('horiz').text='0'; v.find('vert').text='0'
        elif pid in('leftcrop','rightcrop','topcrop','bottomcrop'): v.text=f"{g[pid[0]]:.4f}"
    return f
cid=[0]
def clip(k,start,end,geo,name=None,enabled=True):
    cid[0]+=1; L=end-start
    i0=0 if STILL(k) else int(round((B0-OFF2[k])*FPS))+start
    c=ET.Element('clipitem',id=f'r78c-{cid[0]}')
    ET.SubElement(c,'masterclipid').text='r78-mc-'+safe(k); ET.SubElement(c,'name').text=name or os.path.basename(FILES[k])
    ET.SubElement(c,'enabled').text='TRUE' if enabled else 'FALSE'
    ET.SubElement(c,'duration').text=str(NATIVE[k][2] if STILL(k) else L); c.append(rate())
    for t,v in (('start',start),('end',end),('in',i0),('out',i0+L)): ET.SubElement(c,t).text=str(v)
    c.append(fileel(k))
    if geo is not None: c.append(bm(geo))
    return c
def seq_shell(sid,name,dur):
    s=ET.Element('sequence',id=sid); ET.SubElement(s,'name').text=name; ET.SubElement(s,'duration').text=str(dur); s.append(rate())
    tc=ET.SubElement(s,'timecode'); tc.append(rate()); ET.SubElement(tc,'string').text='00:00:00;00'; ET.SubElement(tc,'frame').text='0'; ET.SubElement(tc,'displayformat').text='DF'
    media=ET.SubElement(s,'media'); vid=ET.SubElement(media,'video')
    fmt=ET.SubElement(ET.SubElement(vid,'format'),'samplecharacteristics'); fmt.append(rate())
    for t,v in (('width','1920'),('height','1080'),('pixelaspectratio','square'),('fielddominance','none')): ET.SubElement(fmt,t).text=v
    return s,media,vid
PIECES=[]
for S in SECT:
    for p in S['pieces']:
        g0,g1=max(0,G(p['m0'])),min(NB,G(p['m1']))
        if g1>g0: PIECES.append([g0,g1,p,S])
if PIECES[-1][1]<NB: PIECES[-1][1]=NB
# guests tight: nudge the frame toward whichever guest mic is talking
FOC=[]
for a,b,s in runs:
    f={2:0.115,3:-0.115}.get(s,0.0)
    g0,g1=G(a),min(NB,G(b))
    if FOC and FOC[-1][2]==f: FOC[-1][1]=g1
    else: FOC.append([g0,g1,f])
FOC[0][0]=0; FOC[-1][1]=NB
TRN={1:'BACKDROP',2:'BORDER post',3:'MATTE',4:'BORDER cam',5:'SPLIT CAM',6:'IG POST'}
def build_angle(i):
    name,kind,cam,sc=ANGLES[i]
    s,media,vid=seq_shell(f'r78-ang-{i}',f'R78 ANG {name}',NB)
    if kind=='full':
        tr=ET.SubElement(vid,'track')
        if i==9:
            for g0,g1,f in FOC: tr.append(clip(cam,g0,g1,full(sc,f)))
        else: tr.append(clip(cam,0,NB,full(sc)))
        ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'; return s
    tracks={t:ET.SubElement(vid,'track') for t in range(1,7)}
    t=0
    for g0,g1,p,S in PIECES+[(NB,NB,None,None)]:
        if g0>t: tracks[1].append(clip(cam,t,g0,full(sc)))
        if p is None: break
        PA=S['PA']; pr=panel(kind,PA)
        tracks[1].append(clip('BG',g0,g1,full(100),name=TRN[1]))
        tracks[2].append(clip('WH',g0,g1,plate(pr,BW),name=TRN[2]))
        tracks[3].append(clip('BK',g0,g1,plate(pr),name=TRN[3]))
        if kind=='A':
            gc,cr=camfit(cam,40,180,pr[0]-70,870)
            tracks[4].append(clip('WH',g0,g1,plate(cr,BW),name=TRN[4])); tracks[5].append(clip(cam,g0,g1,gc,name=TRN[5]))
        elif kind=='B':
            prr=(40,788,488,1040)
            tracks[4].append(clip('WH',g0,g1,plate(prr,BW),name=TRN[4])); tracks[5].append(clip(cam,g0,g1,place((0,0,1920,1080),(40,788),448/19.2),name='PIP CAM'))
        geo=fitc(p['box'],PA,pr)
        if p['kind']=='live': tracks[6].append(clip('OBS',g0,g1,geo,name='IG POST' if S['handle'] else 'SCREEN'))
        else: tracks[6].append(clip('H_'+p['still'],g0,g1,geo,name='HOLD '+p['still']))
        t=g1
    for tr in tracks.values(): ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
    return s
def nest(start,end,inp,enabled,name,mcid):
    cid[0]+=1; L=end-start
    c=ET.Element('clipitem',id=f'r78n-{cid[0]}')
    ET.SubElement(c,'masterclipid').text=mcid; ET.SubElement(c,'name').text=name
    ET.SubElement(c,'enabled').text='TRUE' if enabled else 'FALSE'; ET.SubElement(c,'duration').text=str(NB); c.append(rate())
    for t,v in (('start',start),('end',end),('in',inp),('out',inp+L)): ET.SubElement(c,t).text=str(v)
    return c
defined=set()
def nest_angle(i,start,end,inp,enabled):
    c=nest(start,end,inp,enabled,'ANG '+ANGLES[i][0],f'r78-mc-ang-{i}')
    if i in defined: ET.SubElement(c,'sequence',id=f'r78-ang-{i}')
    else: defined.add(i); c.append(build_angle(i))
    return c

# ================= MAIN =================
FINAL=[]; KEPT=[]; t=INTRO; g=0
while g<NB:
    if removed[g]: g+=1; continue
    h=g
    while h<NB and not removed[h] and ang_g[h]==ang_g[g] and seg_g[h]==seg_g[g]: h+=1
    FINAL.append(dict(start=t,end=t+(h-g),inp=g,ang=int(ang_g[g])))
    if KEPT and KEPT[-1][1]==g: KEPT[-1]=(KEPT[-1][0],h,KEPT[-1][2])
    else: KEPT.append((g,h,t))
    t+=h-g; g=h
NF=t
def g2main(gg):
    for a,b,ts in KEPT:
        if a<=gg<b: return ts+gg-a
        if gg<a: return ts
    return NF
main,media,vid=seq_shell('r78-main','ShopTalk_10-05-26_R78_SWITCHER',NF)
Ffiles={f.get('id'):f for f in FIN.iter('file') if len(f)}; seenF=set()
def intro_items(kind,idx):
    trs=seqF.findall(f'media/{kind}/track'); out=[]
    if idx>=len(trs): return out
    for c in trs[idx]:
        if c.tag not in('clipitem','transitionitem','generatoritem'): continue
        s=int(c.findtext('start')); e=int(c.findtext('end'))
        if not (s<400 and (e<=400 or e<0)): continue
        cc=copy.deepcopy(c)
        if cc.get('id'): cc.set('id','r77intro-'+cc.get('id'))
        for l in cc.findall('link'): cc.remove(l)
        fe=cc.find('file')
        if fe is not None:
            fid=fe.get('id')
            if fid in seenF:
                for ch in list(fe): fe.remove(ch)
            else:
                seenF.add(fid)
                if len(fe)==0 and fid in Ffiles:
                    j=list(cc).index(fe); cc.remove(fe); cc.insert(j,copy.deepcopy(Ffiles[fid]))
        out.append(cc)
    return out
for ti in range(10):
    tr=ET.SubElement(vid,'track')
    for cc in intro_items('video',ti): tr.append(cc)
    for s in FINAL: tr.append(nest_angle(ti,s['start'],s['end'],s['inp'],s['ang']==ti))
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
tr=ET.SubElement(vid,'track')
stack,_,svid=seq_shell('r78-stack','R78 ANGLES - MULTICAM SOURCE',NB)
for i in range(10):
    t2=ET.SubElement(svid,'track'); t2.append(nest_angle(i,0,NB,0,True)); ET.SubElement(t2,'enabled').text='TRUE'; ET.SubElement(t2,'locked').text='FALSE'
for n_,(a,b,ts) in enumerate(KEPT):
    c=nest(ts,ts+(b-a),a,False,'R78 ANGLES - MULTICAM SOURCE','r78-mc-stack')
    if n_==0: c.append(stack)
    else: ET.SubElement(c,'sequence',id='r78-stack')
    tr.append(c)
ET.SubElement(tr,'enabled').text='FALSE'; ET.SubElement(tr,'locked').text='FALSE'
# V12 artist handle cards: one fixed spot (top-left), same size, held for the whole artist segment
tr=ET.SubElement(vid,'track'); cards=[]
for S in SECT:
    if not S['handle']: continue
    a=g2main(max(0,G(S['m0']))); b=NF if S is SECT[-1] else g2main(min(NB,G(S['m1'])))
    cid[0]+=1; k='CARD_'+S['handle']
    c=ET.Element('clipitem',id=f'r78card-{cid[0]}'); ET.SubElement(c,'masterclipid').text='r78-mc-'+safe(k); ET.SubElement(c,'name').text='@'+S['handle']
    ET.SubElement(c,'enabled').text='TRUE'; ET.SubElement(c,'duration').text=str(NATIVE[k][2]); c.append(rate())
    for t_,v in (('start',a),('end',b),('in',0),('out',b-a)): ET.SubElement(c,t_).text=str(v)
    c.append(fileel(k)); tr.append(c); cards.append((S['handle'],a,b))
ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
# AUDIO: A1 mic 1 Nick, A2 mic 2 guest L, A3 mic 3 guest R; intro music copied from the R77 final
aud=ET.SubElement(media,'audio'); ET.SubElement(aud,'numOutputChannels').text='2'
af=ET.SubElement(ET.SubElement(aud,'format'),'samplecharacteristics'); ET.SubElement(af,'depth').text='16'; ET.SubElement(af,'samplerate').text='48000'
MICN={0:('M1','MIC 1 NICK'),1:('M2','MIC 2 GUEST L'),2:('M3','MIC 3 GUEST R')}
for ti in range(8):
    tr=ET.SubElement(aud,'track')
    for cc in intro_items('audio',ti): tr.append(cc)
    if ti in MICN:
        k,nm=MICN[ti]
        for n_,(a,b,ts) in enumerate(KEPT):
            L=b-a; i0=int(round(B0*FPS))+a
            c=ET.SubElement(tr,'clipitem',id=f'r78-mic{ti+1}-{n_}'); ET.SubElement(c,'masterclipid').text='r78-mc-'+k
            ET.SubElement(c,'name').text=nm; ET.SubElement(c,'enabled').text='TRUE'; ET.SubElement(c,'duration').text=str(NATIVE[k][2]); c.append(rate())
            for t_,v in (('start',ts),('end',ts+L),('in',i0),('out',i0+L)): ET.SubElement(c,t_).text=str(v)
            c.append(fileel(k)); st_=ET.SubElement(c,'sourcetrack'); ET.SubElement(st_,'mediatype').text='audio'; ET.SubElement(st_,'trackindex').text='1'
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
main.find('duration').text=str(NF)
# intro title card: ep:77 -> ep:78 (same-length swap inside the Essential Graphics text blob)
import base64
for f in main.iter('filter'):
    if f.findtext('effect/name')=='ep:77':
        f.find('effect/name').text='ep:78'
        for p in f.iter('parameter'):
            if p.findtext('name')=='Source Text':
                b=base64.b64decode(p.findtext('value')); p.find('value').text=base64.b64encode(b.replace(b'ep:77',b'ep:78')).decode()
xm=ET.Element('xmeml',version='4'); xm.append(main); ET.indent(xm,space=' ')
outp=H('~/r78/ShopTalk_10-05-26_R78_SWITCHER.xml')
with open(outp,'w',encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'); f.write(ET.tostring(xm,encoding='unicode'))
ET.parse(outp)
import shutil; shutil.copy(outp,H('~/mnt/Release 78/ShopTalk_10-05-26_R78_SWITCHER.xml'))
tot=Counter()
for s in FINAL: tot[ANGLES[s['ang']][0]]+=(s['end']-s['start'])/FPS
L_=[(s['end']-s['start'])/FPS for s in FINAL]
print('wrote',os.path.getsize(outp)//1024,'KB  NF',NF,'runtime',f"{int(NF/FPS//60)}:{NF/FPS%60:04.1f}",'body',round((NF-INTRO)/FPS,1),'s  shots',len(FINAL),'median',round(float(np.median(L_)),1),'kept ranges',len(KEPT))
for k,v in sorted(tot.items(),key=lambda x:-x[1]): print(f'   {k:28s} {v:6.1f}s')
for h,a,b in cards: print('card @'+h,f'{a/FPS:.1f}-{b/FPS:.1f}s main')
json.dump(dict(FINAL=FINAL,KEPT=KEPT,NF=NF,cards=cards,segs=segs),open('final_r78.json','w'),default=float)
