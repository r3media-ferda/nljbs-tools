"""Render check frames straight from the R78 switcher XML (enabled angle nest + top tracks).
usage: python3 render_check.py XML MEDIA_DIR OUTDIR TAG t1,t2,...   (times = main timeline seconds)"""
import sys, os, subprocess, numpy as np, xml.etree.ElementTree as ET
from urllib.parse import unquote
xmlp, mediadir, outdir, tag = sys.argv[1:5]
times=[float(x) for x in sys.argv[5].split(',')]
FPS=30000/1001; W,H=1920,1080
r=ET.parse(xmlp).getroot(); main=r.find('sequence')
seqs={s.get('id'):s for s in r.iter('sequence') if s.find('media') is not None}
fpath={}
for f in r.iter('file'):
    p=f.findtext('pathurl')
    if p: fpath[f.get('id')]=unquote(p).replace('file://localhost','').replace('file://','').replace('///','/').replace('//Volumes','/Volumes').replace('/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 2',mediadir)
def params(c):
    P=dict(scale=100,cx=0,cy=0,l=0,r=0,t=0,b=0)
    for q in c.findall('.//effect/parameter'):
        pid=q.findtext('parameterid')
        if pid=='scale': P['scale']=float(q.findtext('value'))
        if pid=='center': P['cx']=float(q.findtext('value/horiz')); P['cy']=float(q.findtext('value/vert'))
        if pid in('leftcrop','rightcrop','topcrop','bottomcrop'): P[pid[0]]=float(q.findtext('value'))
    return P
def layers_at(seq,tf,depth=0):
    out=[]
    for tr in seq.findall('media/video/track'):
        if tr.findtext('enabled')!='TRUE' and not (depth==0 and os.environ.get('FORCE')): continue
        for c in tr.findall('clipitem'):
            FORCE=os.environ.get('FORCE')
            nm=c.findtext('name') or ''
            if depth==0 and FORCE and nm.startswith('ANG '):
                if not nm.startswith('ANG '+FORCE+' '): continue
            elif c.findtext('enabled')!='TRUE': continue
            s,e=int(c.findtext('start')),int(c.findtext('end'))
            if not (s<=tf<e): continue
            sq=c.find('sequence')
            if sq is not None:
                inner=seqs[sq.get('id')]; out+=layers_at(inner,int(c.findtext('in'))+tf-s,depth+1)
            else:
                fe=c.find('file')
                if fe is None: continue
                p=fpath.get(fe.get('id'))
                if not p: continue
                out.append(dict(path=p,src_t=(int(c.findtext('in'))+tf-s)/FPS,**params(c)))
    return out
os.makedirs(outdir,exist_ok=True)
for T in times:
    tf=int(T*FPS); canvas=np.full((H,W,3),40,np.float32); desc=[]
    for L in layers_at(main,tf):
        still=L['path'].lower().endswith(('.png','.jpg'))
        st=0 if still else L['src_t']
        x0=int(L['l']/100*W); x1=int(W-L['r']/100*W); y0=int(L['t']/100*H); y1=int(H-L['b']/100*H)
        s=L['scale']/100; cw,ch=x1-x0,y1-y0; ow,oh=max(2,int(cw*s)//2*2),max(2,int(ch*s)//2*2)
        raw=subprocess.run(['ffmpeg','-v','error']+([] if still else ['-ss',f'{st:.3f}'])+['-i',L['path'],'-frames:v','1','-vf',f'scale=1920:1080,crop={cw}:{ch}:{x0}:{y0},scale={ow}:{oh}','-f','rawvideo','-pix_fmt','rgba','-'],capture_output=True); err=raw.stderr.decode()[-300:]; raw=raw.stdout
        if len(raw)<ow*oh*4: desc.append('MISSING '+os.path.basename(L['path'])+' '+err); continue
        img=np.frombuffer(raw,np.uint8)[:ow*oh*4].reshape(oh,ow,4).astype(np.float32)
        PX=W/2+L['cx']*W; PY=H/2+L['cy']*H
        ox=int(round(PX+(x0-W/2)*s)); oy=int(round(PY+(y0-H/2)*s))
        a0,b0=max(0,ox),max(0,oy); a1,b1=min(W,ox+ow),min(H,oy+oh)
        if a1>a0 and b1>b0:
            sub=img[b0-oy:b1-oy,a0-ox:a1-ox]; al=sub[...,3:4]/255
            canvas[b0:b1,a0:a1]=canvas[b0:b1,a0:a1]*(1-al)+sub[...,:3]*al
        desc.append(f"{os.path.basename(L['path'])[:22]}@{st:.1f}")
    fn=f'{outdir}/{tag}_{T:07.1f}.jpg'
    subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-i','-','-q:v','4',fn],input=canvas.clip(0,255).astype(np.uint8).tobytes())
    print(f'{T:7.1f}',' | '.join(desc))
