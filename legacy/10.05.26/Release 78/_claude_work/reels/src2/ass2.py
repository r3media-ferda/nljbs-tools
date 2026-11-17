import json
FR=1001/30000
plan=json.load(open('plan2.json'))
def ts(t):
    t=max(0,t); return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"
RED='&H2A1FD2&'; WHITE='&HFFFFFF&'
for P in plan:
    cap=P['cap']; cap.sort(key=lambda c:c['s'])
    for j,c in enumerate(cap):
        end=max(c['toks'][-1]['e']+0.2,c['s']+0.4)
        if j+1<len(cap): end=min(end,cap[j+1]['s'])
        c['e']=min(end,P['dur'])
    hdr="""[Script Info]
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
    ev=[]
    if P['handle']:
        for s in P['shots']:
            if s['kind']=='T':
                ev.append(f"Dialogue: 1,{ts(s['f0']*FR)},{ts(s['f1']*FR)},Tag,,0,0,0,,{{\\pos(540,330)}}@{P['handle'].upper()}")
    for c in cap:
        txt=' '.join(('{\\c'+RED+'}'+t['t']+'{\\c'+WHITE+'}') if t['k'] else t['t'] for t in c['toks'])
        ev.append(f"Dialogue: 0,{ts(c['s'])},{ts(c['e'])},Cap,,0,0,0,,{{\\pos(540,1170)}}{txt}")
    open(f"R78v2_{P['id']}.ass",'w').write(hdr+'\n'.join(ev)+'\n')
json.dump(plan,open('plan2.json','w'),default=float)
print('ass ok')
