import json
plan=json.load(open('plan.json'))
# ---- ASS files
def ts(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"
for P in plan:
    tattoo = P['kind'] == 'tattoo'
    cy = 1176 if tattoo else 960            # caption baseline center
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Anton,{104 if tattoo else 118},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,7,0,5,40,40,0,1
Style: Tag,Anton,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,4,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    if P['handle']:
        ev.append(f"Dialogue: 1,{ts(0)},{ts(P['dur'])},Tag,,0,0,0,,{{\\pos(540,1046)}}TATTOO BY {{\\c&H00D4FF&}}@{P['handle'].upper()}")
    for c in P['cap']:
        txt = ' '.join(('{\\c&H00D4FF&}' + t['t'] + '{\\c&HFFFFFF&}') if t['k'] else t['t'] for t in c['toks'])
        ev.append(f"Dialogue: 0,{ts(c['s'])},{ts(c['e'])},Cap,,0,0,0,,{{\\pos(540,{cy})\\fad(40,0)}}{txt}")
    open(f"R78_{P['id']}.ass", 'w').write(hdr + '\n'.join(ev) + '\n')

