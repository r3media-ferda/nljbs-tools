"""R78 reels planner: specs.json + word timings + speaker labels + OBS boxes -> plan.json + one .ass per reel.
All source times are MIC time (Left Audio Channel#54.wav starts at 0)."""
import json, re, wave, numpy as np
FPSN, FPSD = 30000, 1001
FR = FPSD / FPSN
words = json.load(open('words_r.json'))
R = json.load(open('specs.json'))
spk = json.load(open('spk.json')); LAB = np.array(spk['lab']); HOP = spk['hop']
boxes = json.load(open('boxes_s3.json'))
OFF = {'AVE': 10.170, '093A': 36.675, 'OBS': -17.701}      # source time = mic time + OFF
CROP = {'S1': (684, 75, 1432, 1080), 'S2': (292, 96, 1168, 1005)}

# ---- energy (10 ms) for silence trimming
w = wave.open('au/Left_Audio_Channel_54_16k.wav')
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
E = 20 * np.log10(np.sqrt((x[:len(x)//160*160].reshape(-1, 160)**2).mean(1)) + 1e-3)
THR = np.percentile(E, 30) + 8
loud = np.convolve(E > THR, np.ones(7), 'same') > 0

def quiet_snap(t, back):
    """nudge an edge into the nearest quiet 10 ms frame within 0.3 s"""
    i = int(t * 100); rng = range(i, i - 30, -1) if back else range(i, i + 30)
    for k in rng:
        if 0 <= k < len(loud) and not loud[k]: return k / 100
    return t

def trim_silence(a, b, mingap=0.6, keep=0.14):
    ia, ib = int(a * 100), int(b * 100); out = []; s = ia; k = ia
    while k < ib:
        if not loud[k]:
            j = k
            while j < ib and not loud[j]: j += 1
            if (j - k) / 100 >= mingap and k > ia and j < ib:
                out.append((s / 100, k / 100 + keep)); s = int(j - keep * 100)
            k = j
        else: k += 1
    out.append((s / 100, ib / 100))
    return [(p, q) for p, q in out if q - p > 0.2]

def speaker_cam(t0, t1):
    """list of (t0,t1,cam) inside [t0,t1]: Nick mic -> AVE, guest mics -> 093A; 1.5 s majority, min run 3 s"""
    a, b = int(t0 / HOP), int(t1 / HOP); seg = LAB[a:b]; out = []
    win = int(1.5 / HOP)
    lab = []
    for i in range(len(seg)):
        wnd = seg[max(0, i - win // 2): i + win // 2]; wnd = wnd[wnd > 0]
        if len(wnd) == 0: lab.append(lab[-1] if lab else 1); continue
        nick = (wnd == 1).sum(); g = (wnd > 1).sum(); lab.append(1 if nick >= g else 2)
    runs = []
    for i, l in enumerate(lab):
        t = t0 + i * HOP
        if runs and runs[-1][2] == l: runs[-1][1] = t + HOP
        else: runs.append([t, t + HOP, l])
    ch = True
    while ch and len(runs) > 1:
        ch = False
        for i, r in enumerate(runs):
            if r[1] - r[0] < 3.0:
                if i == 0: runs[1][0] = r[0]
                elif i == len(runs) - 1: runs[i - 1][1] = r[1]
                elif runs[i - 1][1] - runs[i - 1][0] >= runs[i + 1][1] - runs[i + 1][0]: runs[i - 1][1] = r[1]
                else: runs[i + 1][0] = r[0]
                runs.pop(i); ch = True; break
        m = []
        for r in runs:
            if m and m[-1][2] == r[2]: m[-1][1] = r[1]
            else: m.append(r)
        runs = m
    if runs: runs[0][0] = t0; runs[-1][1] = t1
    return [(r[0], r[1], 'AVE' if r[2] == 1 else '093A') for r in runs]

def s3_box(t0, t1):
    bs = np.array([b[1:] for b in boxes if t0 - 0.5 <= b[0] <= t1 + 0.5])
    if len(bs) == 0: return (360, 60, 1320, 1060)
    x0, y0, x1, y1 = np.median(bs, 0)
    return (int(max(0, x0 - 50)), int(max(60, y0)), int(min(1920, x1 + 50)), int(min(1060, y1)))

def box_runs(t0, t1):
    """split by OBS zoom-state changes (S3); states shorter than 2.5 s fold into a neighbour"""
    ts = [b for b in boxes if t0 <= b[0] <= t1]
    if not ts: return [(t0, t1, s3_box(t0, t1))]
    runs = [[t0, None, ts[0]]]
    for b in ts[1:]:
        ref = runs[-1][2]
        if abs(b[1] - ref[1]) > 120 or abs(b[3] - ref[3]) > 120: runs[-1][1] = b[0]; runs.append([b[0], None, b])
    runs[-1][1] = t1
    ch = True
    while ch and len(runs) > 1:
        ch = False
        for i, r in enumerate(runs):
            if r[1] - r[0] < 2.5:
                if i == 0: runs[1][0] = r[0]
                else: runs[i - 1][1] = r[1]
                runs.pop(i); ch = True; break
    return [(a, c, s3_box(a, c)) for a, c, _ in runs]

# ---- caption text cleanup
FILLER = {'uh', 'um', 'mhm', 'mm', 'huh'}
FIX = {'tesco': 'Chesko', 'tip': 'Tip', 'connor': None}
def norm(s): return re.sub(r"[^a-z0-9']", "", s.lower())
KEY = {
 '01': 'camera pause seventeen pretended didn\'t magic hands video blaine hologram tupac',
 '02': 'eyes knee shorts gap nailed focal drawing pulp love',
 '03': 'doggie unbelievable nose shocking cheesing breathe suffering alive tip',
 '04': 'values last lines structure black gray hold right corgi sad collar happy',
 '05': 'fresh healed heal dark fucked perfect softened lighten needle beautifully',
 '06': 'koi rocks jumping energy simple darks wind clouds eye batteries elbow screamer',
 '07': 'yawning headphone slippers bathroom shirtless costanza comfortable',
}
REPL = {'07': [(('at', 'connor'), '@AECONNER'), (('porter', 'underscore', 'electric'), '@PORTER_ELECTRIC')],
        '05': [(('there\'s', 'no', 'way', 'eddie', 'do', 'it'), None)]}
DROP_07 = {'beside', 'yoongi'}

plan = []
for r in R:
    rid = r['id']
    ranges = [r['hook']] + r['body']
    pieces = []; spans = []
    for n, (a, b) in enumerate(ranges):
        s0 = quiet_snap(words[a]['s'] - 0.12, True); s1 = quiet_snap(words[b]['e'] + 0.28, False)
        if n > 1 and s0 < spans[-1][1] + 0.4:          # body ranges that touch/overlap -> one continuous span
            spans[-1][1] = max(spans[-1][1], s1); spans[-1][3] = b; continue
        spans.append([s0, s1, a, b, n])
    ranges = [(sp[2], sp[3]) for sp in spans]
    for n, (s0, s1, a, b, _) in enumerate(spans):
        for p, q in trim_silence(s0, s1):
            pieces.append(dict(src0=p, src1=q, hook=(n == 0), rng=n))
    # frame-quantize and lay out on reel time
    t = 0.0; frame = 0
    for p in pieces:
        nf = max(1, int(round((p['src1'] - p['src0']) / FR)))
        p['nf'] = nf; p['src1'] = p['src0'] + nf * FR; p['out0'] = frame * FR; frame += nf
        # visual sub-pieces
        subs = []
        if r['kind'] == 'tattoo':
            vis = box_runs(p['src0'], p['src1']) if r['sect'] == 'S3' else [(p['src0'], p['src1'], CROP[r['sect']])]
            for v0, v1, bx in vis:
                subs.append(dict(src0=v0, src1=v1, box=bx, cams=speaker_cam(v0, v1)))
        else:
            subs.append(dict(src0=p['src0'], src1=p['src1']))
        p['subs'] = subs
    total = frame * FR
    # ---- captions (reel time)
    keys = set(norm(k) for k in KEY.get(rid, '').split())
    cap = []
    for p in pieces:
        a, b = ranges[p['rng']]
        idx = [i for i in range(a, b + 1) if p['src0'] - 0.05 <= words[i]['s'] < p['src1']]
        toks = []
        i = 0
        while i < len(idx):
            wi = idx[i]; tk = norm(words[wi]['w'])
            rep = None
            for pat, out in REPL.get(rid, []):
                if tuple(norm(words[j]['w']) for j in idx[i:i + len(pat)]) == pat:
                    rep = (pat, out); break
            if rep:
                if rep[1]: toks.append(dict(t=rep[1], s=words[wi]['s'], e=words[idx[i + len(rep[0]) - 1]]['e'], k=True, p=''))
                i += len(rep[0]); continue
            if tk in FILLER or (rid == '07' and tk in DROP_07): i += 1; continue
            txt = words[wi]['w']
            if tk in FIX and FIX[tk]: txt = FIX[tk]
            toks.append(dict(t=txt.upper(), s=words[wi]['s'], e=words[wi]['e'], k=tk in keys, p=words[wi]['p']))
            i += 1
        for tk in toks:
            tk['s'] = p['out0'] + max(0, tk['s'] - p['src0']); tk['e'] = p['out0'] + min(p['src1'], tk['e']) - p['src0']
        # group into cards (<=3 words, break at punctuation / long gap / 16 chars)
        cur = []
        for j, tk in enumerate(toks):
            cur.append(tk)
            nxt = toks[j + 1] if j + 1 < len(toks) else None
            chars = sum(len(c['t']) + 1 for c in cur)
            if (nxt is None or len(cur) >= 3 or (tk['p'] and tk['p'][-1] in '.?!,') or nxt['s'] - tk['e'] > 0.35
                    or chars + len(nxt['t']) > 16):
                cap.append(dict(s=cur[0]['s'], e=cur[-1]['e'], toks=cur)); cur = []
        if cur: cap.append(dict(s=cur[0]['s'], e=cur[-1]['e'], toks=cur))
    cap.sort(key=lambda c: c['s'])
    mc = []
    for c in cap:                       # flash cards (<0.35 s) merge into the next one
        if mc and mc[-1]['e'] - mc[-1]['s'] < 0.35 and len(mc[-1]['toks']) + len(c['toks']) <= 4 and c['s'] - mc[-1]['e'] < 0.3:
            mc[-1]['toks'] += c['toks']; mc[-1]['e'] = c['e']
        else: mc.append(c)
    cap = mc
    for j, c in enumerate(cap):
        end = max(c['e'] + 0.25, c['s'] + 0.45)
        if j + 1 < len(cap): end = min(end, cap[j + 1]['s'])
        c['e'] = min(end, total)
    plan.append(dict(id=rid, slug=r['slug'], kind=r['kind'], handle=r.get('handle'), title=r['title'],
                     pieces=pieces, frames=frame, dur=round(total, 2), cap=cap))
    print(rid, r['slug'], 'pieces', len(pieces), 'dur', round(total, 1), 's  cards', len(cap))

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
Style: Tag,Anton,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,4,0,5,40,40,0,1

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
json.dump(plan, open('plan.json', 'w'), indent=0, default=float)
