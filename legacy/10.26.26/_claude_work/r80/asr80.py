import numpy as np, sherpa_onnx, json, os, time
M='/tmp/m/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/'
rec=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=M+'encoder.int8.onnx',decoder=M+'decoder.int8.onnx',joiner=M+'joiner.int8.onnx',tokens=M+'tokens.txt',model_type='nemo_transducer',num_threads=4)
SR=16000
x=sum(np.fromfile(f'm{i}.f32',np.float32) for i in (1,2,3))
x*=0.3/(np.percentile(np.abs(x),99.9)+1e-9)
if not os.path.exists('chunks.json'):
    e=np.sqrt(np.convolve(x**2,np.ones(1600)/1600,'same')[::160])
    cuts=[0.0]; t=0
    while t < len(x)/SR-28:
        lo,hi=int((t+18)*100),int((t+28)*100); i=lo+int(np.argmin(e[lo:hi])); t=i/100; cuts.append(t)
    cuts.append(len(x)/SR); json.dump(cuts,open('chunks.json','w'))
cuts=json.load(open('chunks.json'))
out=json.load(open('words80.json')) if os.path.exists('words80.json') else {'done':0,'words':[]}
t0=time.time()
for ci in range(out['done'],len(cuts)-1):
    if time.time()-t0>140: break
    a,b=cuts[ci],cuts[ci+1]; s=rec.create_stream(); s.accept_waveform(SR,x[int(a*SR):int(b*SR)]); rec.decode_stream(s)
    cur=None
    for tk,tt in zip(s.result.tokens,s.result.timestamps):
        if tk.startswith(' ') or cur is None:
            if cur: out['words'].append(cur)
            cur=[tk.strip(),round(a+tt,3)]
        else: cur[0]+=tk
    if cur: out['words'].append(cur)
    out['done']=ci+1
json.dump(out,open('words80.json','w'))
print(out['done'],'/',len(cuts)-1,'words',len(out['words']),'t',round(time.time()-t0))
