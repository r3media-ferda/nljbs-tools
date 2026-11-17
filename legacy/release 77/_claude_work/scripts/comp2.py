import sys, os, subprocess, numpy as np, xml.etree.ElementTree as ET
from urllib.parse import unquote
xmlp, mediadir, outdir, tag = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
times=[float(x) for x in sys.argv[5].split(',')]
FPS=30000/1001; W,H=1920,1080
r=ET.parse(xmlp).getroot(); seq=r.find('sequence')
fpath={}
for f in r.iter('file'):
    p=f.findtext('pathurl')
    if p: fpath[f.get('id')]=os.path.join(mediadir,os.path.basename(unquote(p)))
layers=[]
for ti,tr in enumerate(seq.findall('media/video/track')):
    if tr.findtext('enabled')!='TRUE': continue
    for c in tr.findall('clipitem'):
        fe=c.find('file'); 
        if fe is None or c.findtext('enabled')=='FALSE': continue
        p=fpath.get(fe.get('id')); p=p if (p and os.path.exists(p)) else (os.path.join(mediadir,'R77_PLATES',os.path.basename(p)) if p else None)
        if not p or not os.path.exists(p): continue
        P=dict(scale=100,cx=0,cy=0,l=0,r=0,t=0,b=0,op=100)
        for f in c.findall('.//effect'):
            for q in f.findall('parameter'):
                pid=q.findtext('parameterid')
                if pid=='scale': P['scale']=float(q.findtext('value'))
                if pid=='center': P['cx']=float(q.findtext('value/horiz')); P['cy']=float(q.findtext('value/vert'))
                if pid in('leftcrop','rightcrop','topcrop','bottomcrop'): P[pid[0]]=float(q.findtext('value'))
                if pid=='opacity' and q.findtext('value'): P['op']=float(q.findtext('value'))
        layers.append(dict(tr=ti,s=int(c.findtext('start')),e=int(c.findtext('end')),inp=int(c.findtext('in')),path=p,**P))
os.makedirs(outdir,exist_ok=True)
for T in times:
    tf=int(T*FPS); canvas=np.full((H,W,3),40,np.uint8)
    act=sorted([L for L in layers if L['s']<=tf<L['e']],key=lambda L:L['tr'])
    desc=[]
    for L in act:
        st=0 if L['path'].lower().endswith('.png') else (L['inp']+tf-L['s'])/FPS
        x0=int(L['l']/100*W); x1=int(W-L['r']/100*W); y0=int(L['t']/100*H); y1=int(H-L['b']/100*H)
        s=L['scale']/100; cw,ch=x1-x0,y1-y0; ow,oh=max(2,int(cw*s)//2*2),max(2,int(ch*s)//2*2)
        raw=subprocess.run(['ffmpeg','-v','error','-ss',f'{st:.3f}','-i',L['path'],'-frames:v','1','-vf',f'scale=1920:1080,crop={cw}:{ch}:{x0}:{y0},scale={ow}:{oh}','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
        if len(raw)<ow*oh*3: continue
        img=np.frombuffer(raw,np.uint8)[:ow*oh*3].reshape(oh,ow,3)
        PX=W/2+L['cx']*W; PY=H/2+L['cy']*H
        ox=int(PX+(x0-W/2)*s); oy=int(PY+(y0-H/2)*s)
        a0,b0=max(0,ox),max(0,oy); a1,b1=min(W,ox+ow),min(H,oy+oh)
        if a1>a0 and b1>b0: canvas[b0:b1,a0:a1]=img[b0-oy:b1-oy,a0-ox:a1-ox]
        desc.append(f"{os.path.basename(L['path'])[:10]} out x{a0}-{a1} y{b0}-{b1} (clipped {max(0,ox+ow-W)}px R)")
    fn=f'{outdir}/{tag}_{int(T):05d}.png'
    subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-i','-',fn],input=canvas.tobytes())
    print(T, ' | '.join(desc))
