import numpy as np, os, json, subprocess
D=os.path.expanduser('~/r77'); OBS=os.path.expanduser('~/mnt/release 77/2026-10-05 19-52-42.mp4')
S=json.load(open(f'{D}/states.json'))
keep=[]
for s in S['states']:
    x0,x1,y0,y1=s['box']
    if y1-y0<500 or x0>1150: continue
    t=(s['t0']+s['t1'])/2
    raw=subprocess.run(['ffmpeg','-v','error','-ss',f'{t:.2f}','-i',OBS,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    fr=np.frombuffer(raw,np.uint8).reshape(1080,1920,3).astype(int); lum=fr.mean(2)
    w=x1-x0; kind='reel' if s['box']==[704,1256,84,1068] or (w/(y1-y0)<0.6 and x0>600) else ('zoom' if w>1100 else 'post')
    hdr=None
    if kind=='post':
        rx0,rx1=x1+8,min(1915,x1+540); reg=lum[70:260,rx0:rx1]
        rows=np.where((reg>165).sum(1)>4)[0]
        if len(rows):
            top=70+int(rows[0]); hdr=[int(rx0),int(rx1),int(max(0,top-14)),int(top+52)]
    elif kind=='reel':
        hdr=[int(max(0,x0-380)),int(x0-12),830,1080]
    if hdr:
        c=lum[hdr[2]:hdr[3],hdr[0]:hdr[1]]
        bright=(c>110).mean(); dark=(c<45).mean()
        if not (0.004<bright<0.2 and dark>0.7): hdr=None
    s.update(kind=kind,hdr=hdr,mid=t); keep.append(s)
    print(f"{s['t0']:7.1f}-{s['t1']:7.1f} {kind:5s} box {s['box']} hdr {hdr}")
json.dump(dict(start=S['start'],states=keep),open(f'{D}/states_h.json','w'))
