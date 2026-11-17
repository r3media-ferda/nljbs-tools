from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np, os
H_=os.path.expanduser('~/mnt/')
ANTON=H_+'NLJBS Drive/WORKING SHOP TALM FILES/10.05.26/Release 78/_claude_work/reels/kit1/Anton-Regular.ttf'
CARD=H_+'RECORDING 2/R80_PLATES/card_matty_d_mooney.png'
W,H=1280,720
img=Image.new('RGB',(W,H),(18,18,20))
def L(f): return Image.open(f'hi/f_{f}.jpg').convert('RGB')
def facemean(im,box):
    x,y,w,h=box; a=np.asarray(im.crop((x+w*0.25,y+h*0.35,x+w*0.75,y+h*0.8))).reshape(-1,3).astype(float)
    return a.mean(0)
P=L(1323); PB=(994,162,163,191)
A=L(1300); AB=(375,241,165,197); JB=(1463,375,140,173)
ref=facemean(P,PB)
def match(im,box,boost=1.0):
    m=facemean(im,box); g=np.clip(ref/m,0.7,1.8)*boost
    a=np.asarray(im).astype(float)*g
    # gentle s-curve keeps highlights from clipping
    a=255*(1-np.exp(-a/255*1.6))/(1-np.exp(-1.6))
    return Image.fromarray(np.clip(a,0,255).astype('uint8'))
def strip(im,box,w=233,h=720,fwt=150):
    x,y,fw,fh=box; cx,cy=x+fw/2,y+fh/2; s=fwt/fw
    sw,sh=w/s,h/s; x0=min(max(0,cx-sw/2),1920-sw); y0=min(max(0,cy-sh*0.33),1080-sh)
    c=im.crop((int(x0),int(y0),int(x0+sw),int(y0+sh))).resize((w,h),Image.LANCZOS)
    c=ImageEnhance.Contrast(c).enhance(1.06); c=ImageEnhance.Color(c).enhance(1.08)
    return c.filter(ImageFilter.UnsharpMask(2,60,2))
Pc=ImageEnhance.Contrast(P).enhance(1.0)
img.paste(strip(P,PB),(0,0))
img.paste(strip(match(A,AB),AB),(234,0))
img.paste(strip(match(A,JB),JB),(468,0))
d=ImageDraw.Draw(img)
for x in (233,467): d.rectangle((x,0,x+1,H),fill=(18,18,20))
# right: tiger
T=L(96)
a=np.asarray(T).astype(int); row=a[600]; col=a[:,960]
xs=np.where(row.min(1)>235)[0]; ys=np.where(col.min(1)>235)[0]
print('border xs',xs[:3],xs[-3:],'ys',ys[:3],ys[-3:])
tat=T.crop((618,186,1302,1044))   # 684x858
bg=tat.resize((620,778)).filter(ImageFilter.GaussianBlur(28)); bg=ImageEnhance.Brightness(bg).enhance(0.35)
img.paste(bg.crop((0,29,580,749)),(702,0))
d.rectangle((700,0,703,H),fill=(18,18,20))
card=tat.resize((470,590),Image.LANCZOS)
card=ImageEnhance.Contrast(card).enhance(1.10); card=ImageEnhance.Color(card).enhance(1.08)
bord=Image.new('RGB',(card.width+16,card.height+16),'white'); bord.paste(card,(8,8))
rot=bord.convert('RGBA').rotate(-3,expand=True,resample=Image.BICUBIC)
shadow=rot.split()[-1].point(lambda v:int(v*0.65)).filter(ImageFilter.GaussianBlur(12))
img.paste(Image.new('RGB',rot.size,(0,0,0)),(752,26),shadow)
img.paste(rot,(740,14),rot)
cp=Image.open(CARD).convert('RGBA'); cp=cp.crop(cp.getbbox()); cp=cp.resize((int(cp.width*0.92),int(cp.height*0.92)),Image.LANCZOS)
cb=Image.new('RGBA',(cp.width+12,cp.height+12),'white'); cb.paste(cp,(6,6),cp)
cb=cb.rotate(2,expand=True,resample=Image.BICUBIC); img.paste(cb,(W-cb.width-18,H-cb.height-10),cb)
# bottom gradient under faces for the text
grad=Image.new('L',(700,260)); gd=ImageDraw.Draw(grad)
for y in range(260): gd.line((0,y,700,y),fill=int(240*min(1,(y/260)**1.4)))
img.paste(Image.new('RGB',(700,260),(0,0,0)),(0,460),grad)
F=lambda s: ImageFont.truetype(ANTON,s)
d=ImageDraw.Draw(img)
d.rectangle((18,18,196,74),fill=(220,30,36)); d.text((107,46),'SHOP TALK',font=F(38),fill='white',anchor='mm')
def outline(xy,txt,font,fill,sw=6):
    d.text(xy,txt,font=font,fill=fill,stroke_width=sw,stroke_fill=(0,0,0))
f=F(150); txt='INK MASTER'
w=d.textlength(txt,font=f)
if w>660: f=F(int(150*660/w))
outline((350,690),txt,f,(255,212,0)) if False else d.text((350,688),txt,font=f,fill=(255,212,0),anchor='ms',stroke_width=7,stroke_fill=(0,0,0))
img.save('R80_THUMBNAIL_FINAL.png'); print(img.size, d.textbbox((350,688),txt,font=f,anchor='ms'))
