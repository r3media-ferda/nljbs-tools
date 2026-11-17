import numpy as np, os, json, copy, xml.etree.ElementTree as ET
from urllib.parse import quote
H=os.path.expanduser; D=H('~/r77')
FPS=30000/1001
BASE='/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/release 77/'
T0=82.0; TEND=1496.4; INTRO=400
OFF={'AVE':81.611,'093A':56.070,'C':36.331}
FILES={'AVE':'AVE11878.MP4','093A':'093A2068.MP4','C':'C0003.MP4','OBS':'2026-10-05 19-52-42.mp4',
       'BG':'R77_PLATES/R77_backdrop.png','WH':'R77_PLATES/R77_white.png'}
NATIVE={'AVE':(30,'TRUE',43918),'093A':(30,'TRUE',44817),'C':(120,'TRUE',181320),'OBS':(60,'FALSE',89806),'BG':(30,'TRUE',107892),'WH':(30,'TRUE',107892)}
def F(t): return INTRO+int(round((t-T0)*FPS))
NF=F(TEND)
# ---------- speakers ----------
x=np.fromfile(f'{D}/obs_st.raw',dtype='<i2').reshape(-1,2).astype(np.float32)/32768
h=800;n=len(x)//h
L=20*np.log10(np.sqrt((x[:n*h,0].reshape(n,h)**2).mean(1))+1e-7)
R=20*np.log10(np.sqrt((x[:n*h,1].reshape(n,h)**2).mean(1))+1e-7)
lab=np.where(np.maximum(L,R)<-40,0,np.where(L-R<0.7,1,2))
sm=lab.copy()
for i in range(n):
    w=lab[max(0,i-6):i+7]; w=w[w>0]
    sm[i]=0 if len(w)==0 else (1 if (w==1).sum()>=(w==2).sum() else 2)
# runs on 0.1s grid within body; silence inherits previous
cur=1; seqs=[]
for i in range(int(T0*10),int(TEND*10)):
    s=sm[i] if sm[i]>0 else cur
    cur=s; seqs.append(s)
runs=[]
for k,s in enumerate(seqs):
    t=T0+k*0.1
    if runs and runs[-1][2]==s: runs[-1][1]=t+0.1
    else: runs.append([t,t+0.1,s])
# merge short runs (<1.4s)
changed=True
while changed:
    changed=False
    for i,r in enumerate(runs):
        if r[1]-r[0]<2.2 and len(runs)>1:
            if i>0: runs[i-1][1]=r[1]
            else: runs[i+1][0]=r[0]
            runs.pop(i); changed=True; break
    m=[]
    for r in runs:
        if m and m[-1][2]==r[2]: m[-1][1]=r[1]
        else: m.append(r)
    runs=m
# ---------- full-frame camera shots (speaker follow + wide cutaways + punch-ins) ----------
cams=[]
for a,b,s in runs:
    cam='AVE' if s==1 else '093A'
    d=b-a
    if d>14:
        c0=a+d*0.45; c1=min(b-2.0,c0+3.5)
        cams+= [[a,c0,cam,0],[c0,c1,'C',0],[c1,b,cam,0]]
    else: cams.append([a,b,cam,0])
# punch every 3rd plain shot of a cam
cnt={'AVE':0,'093A':0,'C':0}
for c in cams:
    if c[3]==0:
        cnt[c[2]]+=1
        if cnt[c[2]]%3==0 and c[1]-c[0]>3: c[3]=1
# ---------- layout timeline ----------
S=json.load(open(f'{D}/states_h.json'))['states']
lay=[]  # (t0,t1,mode,state)
for st in S:
    a,b=max(st['t0'],T0),min(st['t1'],TEND)
    if b-a<2.5: continue
    x0,x1,y0,y1=st['box']; ar=(x1-x0)/(y1-y0)
    if st['kind']=='zoom' or ar>1.15:
        t=a; k=0
        while t<b:
            m=['T','A'][k%2]; e=min(b,t+6)
            if b-e<2.5: e=b
            lay.append((t,e,m,st)); t=e; k+=1
        continue
    if b-a<10: lay.append((a,b,'A',st)); continue
    pat=[('A',6),('T',5),('A',7),('F',4)]
    t=a; k=0; usedB=False
    while t<b:
        m,dd=pat[k%len(pat)]
        if m=='T' and k>=5 and b-a>=60 and not usedB: m='B'; usedB=True
        e=min(b,t+dd)
        if b-e<2.5: e=b
        lay.append((t,e,m,st)); t=e; k+=1
# full timeline segments
bounds=sorted(set([T0,TEND]+[c[0] for c in cams]+[c[1] for c in cams]+[l[0] for l in lay]+[l[1] for l in lay]))
bounds=[b for b in bounds if T0<=b<=TEND]
segs=[]
def find(lst,t):
    for e in lst:
        if e[0]<=t<e[1]: return e
    return None
for a,b in zip(bounds[:-1],bounds[1:]):
    if b-a<1e-6: continue
    mid=(a+b)/2; c=find(cams,mid); l=find(lay,mid)
    mode=l[2] if l else 'F'; st=l[3] if l else None
    cam=c[2]; punch=c[3]
    if mode!='F' and cam=='C': cam='AVE' if any(r[0]<=mid<r[1] and r[2]==1 for r in runs) else '093A'
    key=(mode,cam,punch if mode=='F' else 0,id(st) if st else 0)
    if segs and segs[-1]['key']==key: segs[-1]['b']=b
    else: segs.append(dict(a=a,b=b,mode=mode,cam=cam,punch=punch,st=st,key=key))
# absorb fragments < 0.9s into previous
out=[]
for s in segs:
    if out and s['b']-s['a']<1.6: out[-1]['b']=s['b']
    else: out.append(s)
segs=out
for s in segs: s['fa']=F(s['a']); s['fb']=F(s['b'])
segs=[s for s in segs if s['fb']>s['fa']]
for i in range(1,len(segs)): segs[i]['fa']=segs[i-1]['fb']
segs[-1]['fb']=NF
# ---------- geometry ----------
SUBJ={'AVE':(960,900),'093A':(1090,1400),'C':(960,1700)}
FULLSC={'AVE':(107,122),'093A':(111,124),'C':(100,121)}
def place(src,out,scale):
    sx0,sy0,sx1,sy1=src; ox0,oy0=out; s=scale/100
    PX=ox0-(sx0-960)*s; PY=oy0-(sy0-540)*s
    return dict(scale=scale,cx=(PX-960)/1920,cy=(PY-540)/1080,l=sx0/19.2,r=(1920-sx1)/19.2,t=sy0/10.8,b=(1080-sy1)/10.8)
def rect_of(src,out,scale):
    s=scale/100; return (out[0],out[1],out[0]+(src[2]-src[0])*s,out[1]+(src[3]-src[1])*s)
def camfit(cam,bx0,by0,bw,bh):
    cx,mw=SUBJ[cam]; sw=min(1920,max(mw,1080*bw/bh)); sh=min(1080,sw*bh/bw)
    sx0=min(max(0,cx-sw/2),1920-sw); sy0=(1080-sh)*0.35
    sc=bw/sw*100; dh=sh*sc/100
    src=(sx0,sy0,sx0+sw,sy0+sh); out=(bx0,by0+(bh-dh)/2)
    return place(src,out,sc),rect_of(src,out,sc)
def media_src(st,maxar):
    x0,x1,y0,y1=st['box']; w=x1-x0; hh=y1-y0
    if w/hh>maxar: c=(x0+x1)/2; w=hh*maxar; x0=c-w/2; x1=c+w/2
    return (x0,y0,x1,y1)
BW=6
def border(r): return place((0,0,1920,1080),(0,0),100) | {'_rect':(r[0]-BW,r[1]-BW,r[2]+BW,r[3]+BW)}
def white_crop(r):
    x0,y0,x1,y1=[max(0,v) for v in r]; x1=min(1920,x1); y1=min(1080,y1)
    return dict(scale=100,cx=0,cy=0,l=x0/19.2,r=(1920-x1)/19.2,t=y0/10.8,b=(1080-y1)/10.8)
items={k:[] for k in ['V1','V2','V3','V4','V5','V6','V7','V8','V9']}
def add(track,src,fa,fb,t_src_start,geo):
    items[track].append(dict(src=src,fa=fa,fb=fb,ts=t_src_start,geo=geo))
CAMTRACK={'AVE':'V1','093A':'V2','C':'V3'}
for s in segs:
    fa,fb,cam=s['fa'],s['fb'],s['cam']; t=s['a']
    if s['mode']=='F':
        sc=FULLSC[cam][1 if s['punch'] else 0]
        add(CAMTRACK[cam],cam,fa,fb,t-OFF[cam],dict(scale=sc,cx=0,cy=0,l=0,r=0,t=0,b=0)); continue
    st=s['st']; add('V4','BG',fa,fb,0,dict(scale=100,cx=0,cy=0,l=0,r=0,t=0,b=0))
    if s['mode']=='A':
        src=media_src(st,1.0); ar=(src[2]-src[0])/(src[3]-src[1])
        PH=900; PW=PH*ar; px0=1880-PW; py0=150
        g=place(src,(px0,py0),PH/(src[3]-src[1])*100); prect=(px0,py0,1880,py0+PH)
        add('V8','OBS',fa,fb,t,g); add('V5','WH',fa,fb,0,white_crop((prect[0]-BW,prect[1]-BW,prect[2]+BW,prect[3]+BW)))
        bw=px0-30-40; gc,crect=camfit(cam,40,150,bw,900)
        add('V7',cam,fa,fb,t-OFF[cam],gc); add('V6','WH',fa,fb,0,white_crop((crect[0]-BW,crect[1]-BW,crect[2]+BW,crect[3]+BW)))
        if st['hdr']:
            hx0,hx1,hy0,hy1=st['hdr']
            if st['kind']=='reel':
                sc=115; out=(px0-30-(hx1-hx0)*1.15, 1050-(hy1-hy0)*1.15)
            else:
                sc=160; out=(1880-(hx1-hx0)*1.6, 40)
            add('V9','OBS',fa,fb,t,place((hx0,hy0,hx1,hy1),out,sc))
    else:  # B
        src=media_src(st,1.84); ar=(src[2]-src[0])/(src[3]-src[1])
        PH=1000; PW=PH*ar
        if PW>1840: PW=1840; PH=PW/ar
        px0=(1920-PW)/2; py0=(1080-PH)/2
        add('V8','OBS',fa,fb,t,place(src,(px0,py0),PH/(src[3]-src[1])*100))
        add('V5','WH',fa,fb,0,white_crop((px0-BW,py0-BW,px0+PW+BW,py0+PH+BW)))
        pw,ph=448,252; pr=(40,1080-40-ph,40+pw,1080-40)
        add('V7',cam,fa,fb,t-OFF[cam],place((0,0,1920,1080),(40,pr[1]),pw/19.2))
        add('V6','WH',fa,fb,0,white_crop((pr[0]-BW,pr[1]-BW,pr[2]+BW,pr[3]+BW)))
        if st['hdr']:
            hx0,hx1,hy0,hy1=st['hdr']
            if st['kind']=='reel':
                out=(max(20,px0-30-(hx1-hx0)*1.5),40); sc=150
            else:
                out=(px0+20,py0+20); sc=135
            add('V9','OBS',fa,fb,t,place((hx0,hy0,hx1,hy1),out,sc))
json.dump(dict(segs=[{k:v for k,v in s.items() if k not in('st','key')}|{'kind':s['st']['kind'] if s['st'] else None} for s in segs],items=items,NF=NF),open(f'{D}/plan.json','w'),default=float)
from collections import Counter
print('segments',len(segs),'NF',NF,'dur',round((NF-INTRO)/FPS/60,2),'min')
print('modes',Counter(s['mode'] for s in segs),'time',{m:round(sum((s['fb']-s['fa']) for s in segs if s['mode']==m)/FPS,1) for m in 'FAB'})
print('cams (F)',{c:round(sum((s['fb']-s['fa']) for s in segs if s['mode']=='F' and s['cam']==c)/FPS,1) for c in OFF})
L_=[(s['fb']-s['fa'])/FPS for s in segs]; print('shot median',round(float(np.median(L_)),1),'mean',round(float(np.mean(L_)),1),'min',round(min(L_),2))
print('speaker share',Counter(r[2] for r in runs), 'nick time',round(sum(r[1]-r[0] for r in runs if r[2]==1)),'guest',round(sum(r[1]-r[0] for r in runs if r[2]==2)))
