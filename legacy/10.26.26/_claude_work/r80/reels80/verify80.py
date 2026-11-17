import numpy as np, sherpa_onnx, subprocess, re, glob, sys, os, cv2
M='/tmp/m/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/'
rec=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=M+'encoder.int8.onnx',decoder=M+'decoder.int8.onnx',joiner=M+'joiner.int8.onnx',tokens=M+'tokens.txt',model_type='nemo_transducer',num_threads=4)
def norm(s): return re.sub(r"[^a-z0-9]","",s.lower())
for fn in sorted(glob.glob('out/R80_*.mp4')):
    rid=os.path.basename(fn)[4:6]
    a=subprocess.run(['ffmpeg','-v','error','-i',fn,'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout
    x=np.frombuffer(a,np.float32)
    s=rec.create_stream(); s.accept_waveform(16000,x); rec.decode_stream(s)
    words=[];cur=None
    for tk,tt in zip(s.result.tokens,s.result.timestamps):
        if tk.startswith(' ') or cur is None:
            if cur: words.append(cur)
            cur=[tk.strip(),tt]
        else: cur[0]+=tk
    if cur: words.append(cur)
    ev=[]
    for l in open(f'R80_{rid}.ass'):
        if l.startswith('Dialogue: 0'):
            p=l.split(','); t=p[1]; h,m,sx=t.split(':'); st=int(h)*3600+int(m)*60+float(sx)
            txt=re.sub(r'\{[^}]*\}','',l.split(',,0,0,0,,')[-1] if ',,0,0,0,,' in l else l.split(',,')[-1]).strip()
            ev.append((st,txt.split()[0]))
    d=[]
    for st,w0 in ev:
        c=[t for w,t in words if norm(w)==norm(w0) and abs(t-st)<1.0]
        if c: d.append(min(c,key=lambda t:abs(t-st))-st)
    d=np.abs(np.array(d))
    # luma dips
    v=subprocess.run(['ffmpeg','-v','error','-i',fn,'-vf','scale=108:192,format=gray','-f','rawvideo','-'],capture_output=True).stdout
    Y=np.frombuffer(v,np.uint8).reshape(-1,192,108).mean((1,2))
    dips=[i for i in range(1,len(Y)-1) if Y[i]<0.8*Y[i-1] and Y[i]<0.8*Y[i+1]]
    r=subprocess.run(['ffmpeg','-nostdin','-i',fn,'-af','ebur128=peak=true','-f','null','-'],capture_output=True,text=True).stderr
    I=[l for l in r.splitlines() if l.strip().startswith('I:')][-1].split()[1]; TP=[l for l in r.splitlines() if l.strip().startswith('Peak:')][-1].split()[1]
    print(rid,'dur %.1f'%(len(x)/16000),'cards',len(ev),'matched',len(d),'median %.3f p90 %.3f max %.3f'%(np.median(d),np.percentile(d,90),d.max()),'dips',dips,'LUFS',I,'TP',TP)
    print('   ASR:',s.result.text[:160])
    # contact sheet 1 fps
    n=int(len(x)/16000); ims=[]
    for t in range(0,n):
        raw=subprocess.run(['ffmpeg','-v','error','-ss',str(t+0.5),'-i',fn,'-frames:v','1','-vf','scale=180:320','-f','rawvideo','-pix_fmt','bgr24','-'],capture_output=True).stdout
        if len(raw)==180*320*3: im=np.frombuffer(raw,np.uint8).reshape(320,180,3).copy(); cv2.putText(im,str(t),(4,20),0,0.6,(0,255,255),2); ims.append(im)
    while len(ims)%12: ims.append(np.zeros((320,180,3),np.uint8))
    cv2.imwrite(f'out/sheet_{rid}.jpg',np.vstack([np.hstack(ims[i:i+12]) for i in range(0,len(ims),12)]),[cv2.IMWRITE_JPEG_QUALITY,75])
