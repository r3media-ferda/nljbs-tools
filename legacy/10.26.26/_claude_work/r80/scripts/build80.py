# build80.py — Shop Talk 10.26.26 RECORDING 2 (R80): Porter + AC + Jake Hawk (couch). Based on build_r79_final.py.
# Cameras: AVE = AC + Jake two-shot, 093A = Porter single, C0012 = wide three-shot. Jake/AC singles = crops of AVE.
import json, os, copy, sys, base64, numpy as np, xml.etree.ElementTree as ET
from urllib.parse import quote
from collections import Counter
os.chdir('/tmp/r80')
FPS=30000/1001; INTRO=400; TK=8475667200
P=json.load(open('plan_base.json')); B0,B1=P['B0'],P['B1']; OFF=P['OFF']; SECT=P['SECT']; OUT0=P['OUT0']
NB=int(round((B1-B0)*FPS))
def G(m): return int(round((m-B0)*FPS))
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 2/'
MD='NUMBER 2.band/Media/Audio Files/'
FILES={'AVE':'AVE14202.MP4','093A':'093A6724.MP4','C':'C0012.MP4','OBS':'2026-10-26 18-33-39.mp4',
 'M1':MD+'Mic 1 #54.wav','M2':MD+'Mic 2 #54.wav','M3':MD+'Mic 3 #53.wav',
 'BG':'R80_PLATES/R80_backdrop.png','WH':'R80_PLATES/R80_white.png','BK':'R80_PLATES/R80_black.png'}
for S in SECT: FILES['CARD_'+S['handle']]='R80_PLATES/card_%s.png'%S['handle']
VD={'AVE':(1641.306333,FPS,30,'TRUE'),'093A':(1659.691367,FPS,30,'TRUE'),'C':(1690.19,4*FPS,120,'TRUE'),'OBS':(1810.818,60,60,'FALSE')}
NATIVE={k:(tb,nt,int(round(d*f))) for k,(d,f,tb,nt) in VD.items()}
for k in ('M1','M2','M3'): NATIVE[k]=(30,'TRUE',int(1732.0*FPS))
for h in P['holds']: FILES['H_'+h['f']]='R80_PLATES/holds/'+h['f']
def STILL(k): return k in('BG','WH','BK') or k.startswith('CARD_') or k.startswith('H_')
for k in FILES:
    if STILL(k): NATIVE[k]=(30,'TRUE',107892)
OFF2={'AVE':OFF['AVE'],'093A':OFF['093A'],'C':OFF['C'],'OBS':OFF['OBS'],'M1':0.0,'M2':0.0,'M3':0.0}

# ================= EDIT DECISIONS =================
runs=P['runs']
CAM={1:'093A',2:'AVE',3:'AVE'}     # mic 1 Porter -> 093A ; mic 2 AC / mic 3 Jake -> AVE two-shot
OTHER={'093A':'AVE','AVE':'093A'}
shots=[]
for a,b,s in runs:
    cam=CAM[s]; d=b-a
    if d>8:   # long runs: wide or the other camera's reaction in the middle
        c0=a+d*0.45; c1=min(b-2.0,c0+3.5)
        alt=OTHER[cam] if len(shots)%3==2 else 'C'
        shots+=[[a,c0,cam,0,s],[c0,c1,alt,0,s],[c1,b,cam,0,s]]
    else: shots.append([a,b,cam,0,s])
cnt=0
for sh in shots:
    if sh[2]=='AVE':      # AC / Jake share a camera -> punch to the talker's tight now and then (short shots only)
        cnt+=1
        if cnt%6==0 and 4<sh[1]-sh[0]<9 and sh[0]<OUT0: sh[3]=1
# screen layout cycle: A split speaker / S split wide / T tattoo only / F full cam  (R79 final: more wide, less tattoo-only)
PAT=[('A',8),('S',6),('A',8),('F',5),('A',8),('T',4),('A',8),('F',5),('S',6),('A',8),('F',5)]
lay=[]
for S in SECT:
    a=max(S['m0'],B0); b=min(S['m1'],B1,OUT0); t=a; k=0
    while t<b-0.01:
        m,dd=PAT[k%len(PAT)]; e=min(b,t+dd)
        if b-e<2.5: e=b
        lay.append([t,e,m,S['id']]); t=e; k+=1
def find(lst,t):
    for e in lst:
        if e[0]<=t<e[1]: return e
    return None
bounds=sorted(set([B0,B1]+[x for s in shots for x in s[:2]]+[x for l in lay for x in l[:2]]))
bounds=[x for x in bounds if B0<=x<=B1]
# ANG: 0 AC+JAKE, 1 PORTER, 2 WIDE, 3 SPLIT AC+JAKE, 4 SPLIT PORTER, 5 SPLIT WIDE, 6 TATTOO+WIDE PIP, 7 TATTOO ONLY, 8 AC TIGHT, 9 JAKE TIGHT
segs=[]
for a,b in zip(bounds[:-1],bounds[1:]):
    if b-a<1e-6: continue
    mid=(a+b)/2; c=find(shots,mid); l=find(lay,mid)
    mode=l[2] if l else 'F'
    cam,punch,spk=c[2],c[3],c[4]
    if mode=='A' and cam=='C': mode='S'
    if mode=='F': ang={'AVE':(8 if spk==2 else 9) if punch else 0,'093A':1,'C':2}[cam]
    elif mode=='A': ang=3 if cam=='AVE' else 4
    elif mode=='S': ang=5
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

# ================= HYPE TRAILER (cold open) =================
L=np.load('lev80.npy'); E=10*np.log10(sum(10**(L[i]/10) for i in range(3)))   # 10 ms frames, centred +25 ms
def snap(t):
    i=int(round(t*100))-2; w=E[i-6:i+7]; return (i-6+int(np.argmin(w))+2)/100
TRAILER=[(103.50,106.32,0,None),                    # "We're not here to talk about fucking homemade knucklebags."
         (110.42,111.95,1,None),                    # "So Nick's not with us this week."
         (329.55,334.55,7,'matty_d_mooney'),        # "clouds, rocks, berries, tiger... all within a four-inch space"
         (457.85,461.35,7,'matty_d_mooney'),        # "canine teeth are gangster, dude."
         (700.90,703.66,3,'jeremiahbarba'),         # "Definitely go down that rabbit hole because it will fuck you up, man."
         (838.92,842.32,7,'jeremiahbarba'),         # "it's reminiscent of that stuff, but you ain't never seen that motherfucker before."
         (928.48,930.95,4,'cololopeztattoo'),       # "What can Colo not do?"
         (988.33,991.30,7,'cololopeztattoo'),       # "it's like the ghost of the subway, so smart."
         (1406.78,1408.31,2,None)]                  # "that's a super leap of faith."
VIDAT={}; NOSNAP={110.42,1408.31}
TR=[]; t=0
for a,b,ang,card in TRAILER:
    a2=a if a in NOSNAP else snap(a); b2=b if b in NOSNAP else snap(b)
    ga,gb=G(a2),G(b2); gv=G(VIDAT[a]) if a in VIDAT else ga
    TR.append(dict(a=a2,b=b2,ga=ga,gb=gb,gv=gv,ang=ang,card=card,start=t,end=t+gb-ga)); t+=gb-ga
TRL=t
print('trailer',TRL,'frames',round(TRL/FPS,1),'s')

# ================= GEOMETRY =================
BW=6
def place(src,out,scale):
    sx0,sy0,sx1,sy1=src; ox0,oy0=out; s=scale/100
    PX=ox0-(sx0-960)*s; PY=oy0-(sy0-540)*s
    return dict(scale=scale,cx=(PX-960)/1920,cy=(PY-540)/1080,l=sx0/19.2,r=(1920-sx1)/19.2,t=sy0/10.8,b=(1080-sy1)/10.8)
def full(sc,cx=0.0,cy=0.0): return dict(scale=sc,cx=cx,cy=cy,l=0,r=0,t=0,b=0)
def tight(x0,y0,s):   # fill the frame from a 1920/s x 1080/s source window
    w,h=1920/s,1080/s; return place((x0,y0,x0+w,y0+h),(0,0),s*100)
def plate(r,pad=0):
    x0,y0,x1,y1=r; x0=max(0,x0-pad); y0=max(0,y0-pad); x1=min(1920,x1+pad); y1=min(1080,y1+pad)
    return dict(scale=100,cx=0,cy=0,l=x0/19.2,r=(1920-x1)/19.2,t=y0/10.8,b=(1080-y1)/10.8)
SUBJ={'AVE':(1047,1450),'093A':(1130,900),'C':(915,1500)}   # (subject centre x, min source width) for the split box
def camfit(cam,bx0,by0,bw,bh):
    cx,mw=SUBJ[cam]; sw=min(1920,max(mw,1080*bw/bh)); sh=min(1080,sw*bh/bw)
    sx0=min(max(0,cx-sw/2),1920-sw); sy0=(1080-sh)*0.35; sc=bw/sw*100; dh=sh*sc/100
    out=(bx0,by0+(bh-dh)/2); return place((sx0,sy0,sx0+sw,sy0+sh),out,sc),(out[0],out[1],out[0]+bw,out[1]+dh)
def panel(mode,PA):
    PH=870; PW=PH*PA
    if mode=='T': return (960-PW/2,180,960+PW/2,1050)
    return (1880-PW,180,1880,1050)
def fitc(box,PA,pr):
    x0,y0,x1,y1=box; w=x1-x0; h=y1-y0
    if w/h>PA: c=(x0+x1)/2; w=h*PA; x0=c-w/2; x1=c+w/2
    else: c=(y0+y1)/2; h=w/PA; y0=c-h/2; y1=c+h/2
    PW=pr[2]-pr[0]; PH=pr[3]-pr[1]; s=min(PW/(x1-x0),PH/(y1-y0))
    ox=pr[0]+(PW-(x1-x0)*s)/2; oy=pr[1]+(PH-(y1-y0)*s)/2
    return place((x0,y0,x1,y1),(ox,oy),s*100)
# AVE faces (YuNet): AC ~(580,345) w170, Jake ~(1515,470) w138
ANGLES=[('1 AC + JAKE','full','AVE',full(100)),('2 PORTER','full','093A',full(104,-0.01,0)),('3 WIDE','full','C',full(100)),
 ('4 SPLIT - AC + JAKE + TATTOO','A','AVE',None),('5 SPLIT - PORTER + TATTOO','A','093A',None),('6 SPLIT - WIDE + TATTOO','A','C',None),
 ('7 TATTOO + WIDE PIP','B','C',None),('8 TATTOO ONLY','T','C',None),
 ('9 AC TIGHT','full','AVE',tight(32,110,1.75)),('10 JAKE TIGHT','full','AVE',tight(909.5,243,1.9))]
FULLSC={'AVE':full(100),'093A':full(104,-0.01,0),'C':full(100)}

# ================= XML HELPERS =================
FIN=ET.parse(os.path.expanduser('~/r78ref/ShopTalk_10-05-26_R78_EDIT_FIXED.xml')).getroot(); seqF=FIN.find('sequence')
bm_tpl=next(f for c in FIN.iter('clipitem') for f in c.findall('filter') if f.findtext('effect/effectid')=='basic' and f.find(".//parameter[parameterid='leftcrop']") is not None)
def rate(tb=30,nt='TRUE'):
    r=ET.Element('rate'); ET.SubElement(r,'timebase').text=str(tb); ET.SubElement(r,'ntsc').text=nt; return r
def safe(k): return ''.join(ch if ch.isalnum() else '_' for ch in k)
used=set()
def fileel(k):
    fe=ET.Element('file',id='r80-file-'+safe(k))
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
    cid[0]+=1; L_=end-start
    i0=0 if STILL(k) else int(round((B0-OFF2[k])*FPS))+start
    c=ET.Element('clipitem',id=f'r80c-{cid[0]}')
    ET.SubElement(c,'masterclipid').text='r80-mc-'+safe(k); ET.SubElement(c,'name').text=name or os.path.basename(FILES[k])
    ET.SubElement(c,'enabled').text='TRUE' if enabled else 'FALSE'
    ET.SubElement(c,'duration').text=str(NATIVE[k][2] if STILL(k) else L_); c.append(rate())
    for t_,v in (('start',start),('end',end),('in',i0),('out',i0+L_)): ET.SubElement(c,t_).text=str(v)
    c.append(fileel(k))
    if geo is not None: c.append(bm(geo))
    return c
def seq_shell(sid,name,dur):
    s=ET.Element('sequence',id=sid); ET.SubElement(s,'name').text=name; ET.SubElement(s,'duration').text=str(dur); s.append(rate())
    tc=ET.SubElement(s,'timecode'); tc.append(rate()); ET.SubElement(tc,'string').text='00:00:00;00'; ET.SubElement(tc,'frame').text='0'; ET.SubElement(tc,'displayformat').text='DF'
    media=ET.SubElement(s,'media'); vid=ET.SubElement(media,'video')
    fmt=ET.SubElement(ET.SubElement(vid,'format'),'samplecharacteristics'); fmt.append(rate())
    for t_,v in (('width','1920'),('height','1080'),('pixelaspectratio','square'),('fielddominance','none')): ET.SubElement(fmt,t_).text=v
    return s,media,vid
PIECES=[]
for S in SECT:
    for p in S['pieces']:
        g0,g1=max(0,G(p['m0'])),min(NB,G(p['m1']))
        if g1>g0: PIECES.append([g0,g1,p,S])
TRN={1:'BACKDROP',2:'BORDER post',3:'MATTE',4:'BORDER cam',5:'SPLIT CAM',6:'IG POST'}
def build_angle(i):
    name,kind,cam,geo=ANGLES[i]
    s,media,vid=seq_shell(f'r80-ang-{i}',f'R80 ANG {name}',NB)
    if kind=='full':
        tr=ET.SubElement(vid,'track'); tr.append(clip(cam,0,NB,geo))
        ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'; return s
    tracks={t_:ET.SubElement(vid,'track') for t_ in range(1,7)}
    t_=0
    for g0,g1,p,S in PIECES+[(NB,NB,None,None)]:
        if g0>t_: tracks[1].append(clip(cam,t_,g0,FULLSC[cam]))
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
        if p['kind']=='live': tracks[6].append(clip('OBS',g0,g1,geo,name='IG POST'))
        else: tracks[6].append(clip('H_'+p['still'],g0,g1,geo,name='HOLD '+p['still']))
        t_=g1
    for tr in tracks.values(): ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
    return s
def nest(start,end,inp,enabled,name,mcid):
    cid[0]+=1; L_=end-start
    c=ET.Element('clipitem',id=f'r80n-{cid[0]}')
    ET.SubElement(c,'masterclipid').text=mcid; ET.SubElement(c,'name').text=name
    ET.SubElement(c,'enabled').text='TRUE' if enabled else 'FALSE'; ET.SubElement(c,'duration').text=str(NB); c.append(rate())
    for t_,v in (('start',start),('end',end),('in',inp),('out',inp+L_)): ET.SubElement(c,t_).text=str(v)
    return c
defined=set()
def nest_angle(i,start,end,inp,enabled):
    c=nest(start,end,inp,enabled,'ANG '+ANGLES[i][0],f'r80-mc-ang-{i}')
    if i in defined: ET.SubElement(c,'sequence',id=f'r80-ang-{i}')
    else: defined.add(i); c.append(build_angle(i))
    return c

# ================= MAIN =================
BODY0=TRL+INTRO
FINAL=[]; KEPT=[]; t=BODY0; g=0
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
main,media,vid=seq_shell('r80-main','ShopTalk_10-26-26_R80_SWITCHER',NF)
Ffiles={f.get('id'):f for f in FIN.iter('file') if len(f)}; seenF=set()
def shift(cc,dt):
    for tag in ('start','end'):
        e=cc.find(tag)
        if e is not None and int(e.text)>=0: e.text=str(int(e.text)+dt)
def intro_items(kind,idx):
    trs=seqF.findall(f'media/{kind}/track'); out=[]
    if idx>=len(trs): return out
    for c in trs[idx]:
        if c.tag not in('clipitem','transitionitem','generatoritem'): continue
        s_=int(c.findtext('start')); e_=int(c.findtext('end'))
        if not (s_<400 and (e_<=400 or e_<0)): continue
        cc=copy.deepcopy(c)
        if cc.get('id'): cc.set('id','r78intro-'+cc.get('id'))
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
        shift(cc,TRL); out.append(cc)
    return out
for ti in range(10):
    tr=ET.SubElement(vid,'track')
    for T in TR: tr.append(nest_angle(ti,T['start'],T['end'],T['gv'],T['ang']==ti))
    for cc in intro_items('video',ti): tr.append(cc)
    for s_ in FINAL: tr.append(nest_angle(ti,s_['start'],s_['end'],s_['inp'],s_['ang']==ti))
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
# V11 multicam source (disabled)
tr=ET.SubElement(vid,'track')
stack,_,svid=seq_shell('r80-stack','R80 ANGLES - MULTICAM SOURCE',NB)
for i in range(10):
    t2=ET.SubElement(svid,'track'); t2.append(nest_angle(i,0,NB,0,True)); ET.SubElement(t2,'enabled').text='TRUE'; ET.SubElement(t2,'locked').text='FALSE'
first=True
for T in [dict(start=T['start'],end=T['end'],ga=T['gv']) for T in TR]+[dict(start=ts,end=ts+(b-a),ga=a) for a,b,ts in KEPT]:
    c=nest(T['start'],T['end'],T['ga'],False,'R80 ANGLES - MULTICAM SOURCE','r80-mc-stack')
    if first: c.append(stack); first=False
    else: ET.SubElement(c,'sequence',id='r80-stack')
    tr.append(c)
ET.SubElement(tr,'enabled').text='FALSE'; ET.SubElement(tr,'locked').text='FALSE'
# V12 handle cards (top right; slides over the centred tattoo-only panel) + outro shout-outs
tr=ET.SubElement(vid,'track'); cards=[]
PA_OF={S['handle']:S['PA'] for S in SECT}
def card_item(h,a,b,dx):
    cid[0]+=1; k='CARD_'+h
    c=ET.Element('clipitem',id=f'r80card-{cid[0]}'); ET.SubElement(c,'masterclipid').text='r80-mc-'+safe(k); ET.SubElement(c,'name').text='@'+h
    ET.SubElement(c,'enabled').text='TRUE'; ET.SubElement(c,'duration').text=str(NATIVE[k][2]); c.append(rate())
    for t_,v in (('start',a),('end',b),('in',0),('out',b-a)): ET.SubElement(c,t_).text=str(v)
    c.append(fileel(k))
    if dx: c.append(bm(dict(scale=100,cx=dx/1920,cy=0,l=0,r=0,t=0,b=0)))
    return c
def dx_of(h): PW=870*PA_OF[h]; return 960-(1880-PW/2)
for T in TR:
    if T['card']: tr.append(card_item(T['card'],T['start'],T['end'],dx_of(T['card']) if T['ang']==7 else 0))
for S in SECT:
    a=g2main(max(0,G(S['m0']))); b=g2main(min(NB,G(S['m1'])))
    cuts_=[a]+sorted(set(x for f_ in FINAL if f_['ang']==7 and f_['end']>a and f_['start']<b for x in (max(a,f_['start']),min(b,f_['end']))))+[b]
    for p0,p1 in zip(cuts_[:-1],cuts_[1:]):
        if p1<=p0: continue
        isT=any(f_['ang']==7 and f_['start']<=p0 and f_['end']>=p1 for f_ in FINAL)
        tr.append(card_item(S['handle'],p0,p1,dx_of(S['handle']) if isT else 0))
    cards.append((S['handle'],a,b))
# outro shout-outs: R78's BlackTakora graphics, re-timed to when they say them
gfx=[c for c in seqF.findall('media/video/track')[11].findall('clipitem') if c.findtext('name')=='Graphic']
SHOUT={'@aeconner':(1544.60,1550.00),'Porter_electric':(1466.60,1472.50)}
for c in gfx:
    nm=c.findtext('filter/effect/name')
    if nm not in SHOUT: continue
    a,b=SHOUT[nm]; s_=g2main(G(a)); e_=g2main(G(b))
    cc=copy.deepcopy(c); cc.set('id','r80gfx-'+safe(nm))
    for l in cc.findall('link'): cc.remove(l)
    i0=int(cc.findtext('in'))
    cc.find('start').text=str(s_); cc.find('end').text=str(e_); cc.find('out').text=str(i0+e_-s_)
    if cc.find('pproTicksIn') is not None: cc.find('pproTicksIn').text=str(i0*TK); cc.find('pproTicksOut').text=str((i0+e_-s_)*TK)
    fe=cc.find('file'); fid=fe.get('id')
    if fid in seenF: [fe.remove(ch) for ch in list(fe)]
    else:
        seenF.add(fid)
        if len(fe)==0: j=list(cc).index(fe); cc.remove(fe); cc.insert(j,copy.deepcopy(Ffiles[fid]))
    tr.append(cc)
items=sorted(tr.findall('clipitem'),key=lambda c:int(c.findtext('start')))
for c in tr.findall('clipitem'): tr.remove(c)
for c in items: tr.append(c)
ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
# AUDIO: A1 MIC 1 PORTER, A3 MIC 2 AC, A5 MIC 3 JAKE (other tracks = intro music copied from R78)
aud=ET.SubElement(media,'audio'); ET.SubElement(aud,'numOutputChannels').text='2'
af=ET.SubElement(ET.SubElement(aud,'format'),'samplecharacteristics'); ET.SubElement(af,'depth').text='16'; ET.SubElement(af,'samplerate').text='48000'
MICN={0:('M1','MIC 1 PORTER'),2:('M2','MIC 2 AC'),4:('M3','MIC 3 JAKE')}
NA=len(seqF.findall('media/audio/track'))
for ti in range(NA):
    tr=ET.SubElement(aud,'track')
    if ti in MICN:
        k,nm=MICN[ti]
        for n_,(a,b,ts) in enumerate([(T['ga'],T['gb'],T['start']) for T in TR]+KEPT):
            L_=b-a; i0=int(round(B0*FPS))+a
            c=ET.SubElement(tr,'clipitem',id=f'r80-mic{ti+1}-{n_}'); ET.SubElement(c,'masterclipid').text='r80-mc-'+k
            ET.SubElement(c,'name').text=nm; ET.SubElement(c,'enabled').text='TRUE'; ET.SubElement(c,'duration').text=str(NATIVE[k][2]); c.append(rate())
            for t_,v in (('start',ts),('end',ts+L_),('in',i0),('out',i0+L_)): ET.SubElement(c,t_).text=str(v)
            c.append(fileel(k)); st_=ET.SubElement(c,'sourcetrack'); ET.SubElement(st_,'mediatype').text='audio'; ET.SubElement(st_,'trackindex').text='1'
    for cc in intro_items('audio',ti): tr.append(cc)
    items=sorted(tr.findall('clipitem'),key=lambda c:int(c.findtext('start')))
    for c in tr.findall('clipitem'): tr.remove(c)
    for c in items: tr.append(c)
    ET.SubElement(tr,'enabled').text='TRUE'; ET.SubElement(tr,'locked').text='FALSE'
main.find('duration').text=str(NF)
for f in main.iter('filter'):
    if f.findtext('effect/name')=='ep:78':
        f.find('effect/name').text='ep:80'
        for p in f.iter('parameter'):
            if p.findtext('name')=='Source Text':
                b=base64.b64decode(p.findtext('value')); p.find('value').text=base64.b64encode(b.replace(b'ep:78',b'ep:80')).decode()
xm=ET.Element('xmeml',version='4'); xm.append(main); ET.indent(xm,space=' ')
outp='/tmp/r80/ShopTalk_10-26-26_R80_SWITCHER.xml'
with open(outp,'w',encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'); f.write(ET.tostring(xm,encoding='unicode'))
ET.parse(outp)
tot=Counter()
for s_ in FINAL: tot[ANGLES[s_['ang']][0]]+=(s_['end']-s_['start'])/FPS
L2=[(s_['end']-s_['start'])/FPS for s_ in FINAL]
def tc(f): s=f/FPS; return f"{int(s//60)}:{s%60:05.2f}"
print('wrote',os.path.getsize(outp)//1024,'KB  runtime',tc(NF),'trailer',tc(TRL),'intro ends',tc(BODY0),'shots',len(FINAL),'median',round(float(np.median(L2)),1))
for k,v in sorted(tot.items(),key=lambda x:-x[1]): print(f'   {k:30s} {v:6.1f}s')
for h,a,b in cards: print('card @'+h,tc(a),'-',tc(b))
for T in TR: print('TR',tc(T['start']),'-',tc(T['end']),ANGLES[T['ang']][0],T['card'] or '','mic %.2f-%.2f'%(T['a'],T['b']))
json.dump(dict(FINAL=FINAL,KEPT=KEPT,NF=NF,TR=TR,TRL=TRL,BODY0=BODY0,cards=cards),open('final_r80.json','w'),default=float)
