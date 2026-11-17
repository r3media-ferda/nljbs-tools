import numpy as np, subprocess, json, sys, os
OBS=sys.argv[1]; OUT=sys.argv[2]; wins=[(800,872),(1008,1128)]
res=[]
for a,b in wins:
    raw=subprocess.run(['ffmpeg','-v','error','-ss',str(a-17.701),'-t',str(b-a),'-i',OBS,'-vf','fps=2,scale=480:270','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    fr=np.frombuffer(raw,np.uint8).reshape(-1,270,480,3).astype(np.int16)
    for k,f in enumerate(fr):
        mx=f.max(2); mn=f.min(2); act=(mx>55)|((mx-mn)>35)
        reg=act[20:262]
        col=reg.mean(0); cs=np.convolve(col>0.45,np.ones(5)/5,'same')>0.5
        # longest run
        best=(0,0);i=0
        while i<480:
            if cs[i]:
                j=i
                while j<480 and cs[j]: j+=1
                if j-i>best[1]-best[0]: best=(i,j)
                i=j
            else: i+=1
        x0,x1=best
        row=act[:,x0:x1].mean(1) if x1>x0 else np.zeros(270)
        rr=np.where(row>0.3)[0]; y0,y1=(rr.min(),rr.max()+1) if len(rr) else (0,270)
        res.append([round(a+k/2,2)]+[int(v)*4 for v in (x0,y0,x1,y1)])
json.dump(res,open(OUT,'w')); print(len(res)); print(res[::12])
