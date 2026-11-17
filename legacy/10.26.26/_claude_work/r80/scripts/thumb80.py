from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
U='/mnt/user-data/uploads/NLJBS Drive/WORKING SHOP TALM FILES/'
T=U+'10.26.26/_claude_work/r80/thumb/'
ANTON=U+'10.05.26/Release 78/_claude_work/reels/kit1/Anton-Regular.ttf'
W,H=1280,720
img=Image.new('RGB',(W,H),(20,20,22))
# right side: blurred dark backdrop from the tattoo
tat=Image.open(T+'obs_868.jpg').convert('RGB')
bg=tat.crop((340,78,1215,1080)).resize((700,800)).filter(ImageFilter.GaussianBlur(30))
bg=ImageEnhance.Brightness(bg).enhance(0.35); img.paste(bg.crop((0,40,580,760)),(700,0))
# faces: three strips, face in upper third
def strip(f,cx,cy,fw,w=234,h=720):
    im=Image.open(T+f).convert('RGB'); s=118/fw   # face ~118 px wide in the strip
    sw,sh=w/s,h/s; x0=min(max(0,cx-sw/2),1920-sw); y0=max(0,cy-sh*0.30); y0=min(y0,1080-sh)
    c=im.crop((int(x0),int(y0),int(x0+sw),int(y0+sh))).resize((w,h),Image.LANCZOS)
    return ImageEnhance.Contrast(c).enhance(1.05)
for i,(f,cx,cy,fw) in enumerate([('p_929.2.jpg',980,328,155),('a_151.0.jpg',602,335,176),('a_1455.3.jpg',1530,467,142)]):
    img.paste(strip(f,cx,cy,fw),(i*234,0))
d=ImageDraw.Draw(img)
for x in (234,468): d.rectangle((x-2,0,x+1,H),fill=(20,20,22))
d.rectangle((700,0,705,H),fill=(20,20,22))
# bottom gradient for the hook
grad=Image.new('L',(702,330)); gd=ImageDraw.Draw(grad)
for y in range(330): gd.line((0,y,702,y),fill=int(235*min(1,(y/330)**1.3)))
img.paste(Image.new('RGB',(702,330),(0,0,0)),(0,390),grad)
# tattoo card tilted with white border
card=tat.crop((360,78,1200,1000)).resize((452,496),Image.LANCZOS)
card=ImageEnhance.Contrast(card).enhance(1.12)
bord=Image.new('RGB',(452+16,496+16),'white'); bord.paste(card,(8,8))
rot=bord.convert('RGBA').rotate(-3.5,expand=True,resample=Image.BICUBIC)
sh=Image.new('RGBA',rot.size,(0,0,0,0)); sh.putalpha(rot.split()[-1].point(lambda a:int(a*0.6)))
img.paste(Image.new('RGB',rot.size,(0,0,0)),(758,32),sh.split()[-1].filter(ImageFilter.GaussianBlur(10)))
img.paste(rot,(748,22),rot)
# IG header card (our handle plate) under the tattoo, white border, slight tilt
cp=Image.open('/mnt/user-data/uploads/RECORDING 2/R80_PLATES/card_jeremiahbarba.png'); cp=cp.crop(cp.getbbox())
cp=cp.resize((int(cp.width*1.08),int(cp.height*1.08)),Image.LANCZOS)
cb=Image.new('RGBA',(cp.width+12,cp.height+12),'white'); cb.paste(cp,(6,6),cp)
cb=cb.rotate(1.5,expand=True,resample=Image.BICUBIC); img.paste(cb,(800,566),cb)
# SHOP TALK tag
F=lambda s: ImageFont.truetype(ANTON,s)
d.rectangle((22,22,246,94),fill=(220,30,36)); d.text((134,58),'SHOP TALK',font=F(46),fill='white',anchor='mm')
# hook
def outline(xy,txt,font,fill):
    x,y=xy
    for dx in range(-4,5,2):
        for dy in range(-4,5,2): d.text((x+dx,y+dy),txt,font=font,fill=(0,0,0))
    d.text(xy,txt,font=font,fill=fill)
outline((26,478),"YOU AIN'T NEVER",F(96),(255,255,255))
outline((26,598),"SEEN THAT BEFORE",F(84),(255,212,0))
img.save('R80_THUMBNAIL.png'); print(img.size)
