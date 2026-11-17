from PIL import Image, ImageDraw, ImageFont
F='/usr/share/fonts/truetype/liberation/'
fb=ImageFont.truetype(F+'LiberationSans-Bold.ttf',27); fr=ImageFont.truetype(F+'LiberationSans-Regular.ttf',22)
CARDS=[('matty_d_mooney','Dagger And Lark Tattoo','hd/prof_412.png',(713,225,77)),
       ('jeremiahbarba','Conclave Art Studio','hd/prof_772.png',(715,183,78)),
       ('cololopeztattoo','Dolmen Madrid','hd/prof_1291.png',(637,217,83))]
for h,sub,src,(cx,cy,r) in CARDS:
    W=max(388,int(110+max(fb.getlength(h),fr.getlength(sub))+30)); H=127
    card=Image.new('RGBA',(1920,1080),(0,0,0,0)); d=ImageDraw.Draw(card)
    x0=1880-W; y0=36
    d.rounded_rectangle((x0,y0,x0+W,y0+H),14,fill=(30,33,38,245))
    av=Image.open(src).convert('RGB').crop((cx-r,cy-r,cx+r,cy+r)).resize((70,70),Image.LANCZOS)
    m=Image.new('L',(70,70),0); ImageDraw.Draw(m).ellipse((0,0,69,69),fill=255)
    card.paste(av,(x0+26,y0+28),m)
    d.text((x0+110,y0+30),h,font=fb,fill=(245,245,245,255))
    d.text((x0+110,y0+68),sub,font=fr,fill=(165,170,176,255))
    card.save(f'plates/card_{h}.png'); print(h,W)
# preview strip
prev=Image.new('RGB',(1300,420),(60,60,60))
for i,(h,*_) in enumerate(CARDS):
    c=Image.open(f'plates/card_{h}.png'); bb=c.getbbox(); prev.paste(c.crop(bb),(20,20+i*135),c.crop(bb))
prev.save('plates/cards_preview.png')
