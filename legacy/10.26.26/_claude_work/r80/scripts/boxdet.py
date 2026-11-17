import cv2, numpy as np, json, glob
runs=json.load(open('stable_runs.json'))
def det(im):
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY).astype(np.float32)
    H,W=g.shape; y0=95  # below browser chrome
    m=cv2.blur(g,(9,9)); sd=np.sqrt(np.maximum(cv2.blur(g*g,(9,9))-m*m,0))
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    img=((sd>5)|(g>75)|((hsv[...,1]>60)&(g>35))).astype(np.float32)
    img[:y0]=0
    col=img[y0:].mean(0); col=np.convolve(col,np.ones(15)/15,'same')
    good=col>0.55
    # longest run
    best=(0,0);i=0
    while i<W:
        if good[i]:
            j=i
            while j<W and good[j]: j+=1
            if j-i>best[1]-best[0]: best=(i,j)
            i=j
        else: i+=1
    x0,x1=best
    row=img[:,x0:x1].mean(1); row=np.convolve(row,np.ones(9)/9,'same'); gr=row>0.55
    ys=np.where(gr)[0]; ys=ys[ys>=y0]
    if len(ys)==0: return None
    # longest run rows
    best=(0,0);i=0
    while i<H:
        if gr[i] and i>=y0:
            j=i
            while j<H and gr[j]: j+=1
            if j-i>best[1]-best[0]: best=(i,j)
            i=j
        else: i+=1
    return [int(x0),int(best[0]),int(x1),int(best[1])]
out=[]
ims=[]
for k,(a,b) in enumerate(runs):
    im=cv2.imread(f'st/{k:03d}.jpg'); bx=det(im); out.append(dict(k=k,a=a,b=b,box=bx))
    t=cv2.resize(im,(480,270)); 
    if bx: cv2.rectangle(t,(bx[0]//4,bx[1]//4),(bx[2]//4,bx[3]//4),(0,255,0),2)
    cv2.putText(t,f'#{k} {a:.0f} {bx}',(4,22),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,255,255),2); ims.append(t)
json.dump(out,open('boxes_auto.json','w'))
for s in range(0,len(ims),20):
    g=ims[s:s+20]+[np.zeros((270,480,3),np.uint8)]*(20-len(ims[s:s+20]))
    cv2.imwrite(f'st/box_{s//20}.jpg',np.vstack([np.hstack(g[r*4:r*4+4]) for r in range(5)]),[cv2.IMWRITE_JPEG_QUALITY,70])
