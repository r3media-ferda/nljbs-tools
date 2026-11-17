import json, re, sys
H='/tmp/reels80'; sys.path.insert(0,H); from specs80 import SPECS, FIX
FPS=30000/1001; FR=1/FPS
PL=json.load(open(H+'/plan80r.json')); SP={s['id']:s for s in SPECS}
HDR="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Black Takora,112,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,7,3,5,40,40,0,1
Style: Tag,Black Takora,100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,6,3,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
def ts(t):
    t=max(0,t); h=int(t//3600); m=int(t%3600//60); s=t%60
    return f"{h}:{m:02d}:{s:05.2f}"
def clean(w):
    w=FIX.get(w,FIX.get(w.rstrip('.,?!'),w))
    return re.sub(r"[^A-Za-z0-9'@_%\- ]","",w).upper().strip()
for P in PL:
    S=SP[P['id']]; red=S['red']; dur=P['frames']*FR
    words=[dict(w,txt=clean(w['w'])) for w in P['words']]; words=[w for w in words if w['txt']]
    cards=[]; cur=[]
    for k,w in enumerate(words):
        cur.append(w)
        nxt=words[k+1] if k+1<len(words) else None
        txt=' '.join(x['txt'] for x in cur)
        brk=(nxt is None or len(cur)>=3 or re.search(r"[.,?!]$",w['w']) or nxt['piece']!=w['piece']
             or nxt['rt']-w['re']>0.3 or len(txt+' '+nxt['txt'])>15)
        if brk: cards.append(cur); cur=[]
    ev=[]
    for k,c in enumerate(cards):
        a=c[0]['rt']; nxt=cards[k+1][0]['rt'] if k+1<len(cards) else dur
        b=nxt if nxt-c[-1]['re']<0.35 else c[-1]['re']+0.15
        b=max(b,a+0.12); b=min(b,dur)
        def col(x):
            parts=x['txt'].split(' ')
            return ' '.join(('{\\c&H2A1FD2&}'+p+'{\\c&HFFFFFF&}') if p.strip("'") in red else p for p in parts)
        txt=' '.join(col(x) for x in c)
        L=len(' '.join(x['txt'] for x in c)); fs='' if L<=12 else f'\\fs{int(112*12/L)}'
        ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\pos(540,1170){fs}}}{txt}")
    tag=[]
    if P['handle']:
        L=len(P['handle'])+1; fs='' if L<=14 else f'\\fs{int(100*14/L)}'
        for s in P['shots']:
            if s['kind']=='T': tag.append(f"Dialogue: 1,{ts(s['f0']*FR+0.03)},{ts(s['f1']*FR)},Tag,,0,0,0,,{{\\pos(540,330)\\fad(150,150){fs}}}@{P['handle'].upper()}")
    open(f"{H}/R80_{P['id']}.ass",'w').write(HDR+'\n'.join(tag+ev)+'\n')
    print(P['id'],len(ev),'cards |',' / '.join(re.sub(r'\{[^}]*\}','',e.split(',,')[-1]) for e in ev[:16]))
