import cv2, numpy as np, json
exec(open('boxdet.py').read().split('out=[]')[0])   # reuse det()
runs=json.load(open('stable_runs.json'))
def expand(im,seed):
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY).astype(np.float32); H,W=g.shape
    gx=np.abs(cv2.Sobel(g,cv2.CV_32F,1,0,ksize=3)); gy=np.abs(cv2.Sobel(g,cv2.CV_32F,0,1,ksize=3))
    x0,y0,x1,y1=seed
    ys=slice(y0+(y1-y0)//8, y1-(y1-y0)//8); xs=slice(x0+(x1-x0)//8, x1-(x1-x0)//8)
    ex=(gx[ys]>20).mean(0); ex=np.maximum(ex,np.maximum(np.roll(ex,1),np.roll(ex,-1)))
    ey=(gy[:,xs]>20).mean(1); ey=np.maximum(ey,np.maximum(np.roll(ey,1),np.roll(ey,-1)))
    T=0.6
    def first(arr,rng):
        for i in rng:
            if arr[i]>T: return i
        return None
    L=first(ex,range(x0+3,max(0,x0-700),-1)); R=first(ex,range(x1-3,min(W-1,x1+700)))
    U=first(ey,range(y0+3,max(90,y0-500),-1)); D=first(ey,range(y1-3,min(H-1,y1+500)))
    return [L if L is not None else x0, U if U is not None else y0, R if R is not None else x1, D if D is not None else y1]
out=[];ims=[]
for k,(a,b) in enumerate(runs):
    im=cv2.imread(f'st/{k:03d}.jpg'); s=det(im); bx=expand(im,s) if s else None
    out.append(dict(k=k,a=a,b=b,seed=s,box=bx))
    t=cv2.resize(im,(480,270))
    if s: cv2.rectangle(t,(s[0]//4,s[1]//4),(s[2]//4,s[3]//4),(0,140,255),1)
    if bx: cv2.rectangle(t,(bx[0]//4,bx[1]//4),(bx[2]//4,bx[3]//4),(0,255,0),2)
    cv2.putText(t,f'#{k} {a:.0f} {bx}',(4,22),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,255,255),2); ims.append(t)
json.dump(out,open('boxes_auto2.json','w'))
for s in range(0,len(ims),20):
    g=ims[s:s+20]+[np.zeros((270,480,3),np.uint8)]*(20-len(ims[s:s+20]))
    cv2.imwrite(f'st/bx2_{s//20}.jpg',np.vstack([np.hstack(g[r*4:r*4+4]) for r in range(5)]),[cv2.IMWRITE_JPEG_QUALITY,70])
