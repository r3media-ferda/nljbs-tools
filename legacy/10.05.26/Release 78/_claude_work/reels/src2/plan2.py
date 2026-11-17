"""R78 reels v2 planner — Avery's reel style (claude/nljbs-reel-style.md):
full-frame shots alternating speaker <-> tattoo every ~2-3.5 s, faces in the upper third, change inside the
first second, BlackTakora captions in the safe zone, @HANDLE on tattoo shots, no dead air.
in: specs2.json, words_r.json, spk.json, boxes_s3.json, au/Left_Audio_Channel_54_16k.wav
out: plan2.json + R78v2_<id>.ass"""
import json, re, wave, numpy as np
FR = 1001 / 30000
words = json.load(open('words_r.json')); R = json.load(open('specs2.json'))
for i in range(1, len(words)):           # alignment can leave words out of order -> force monotonic times
    if words[i]['s'] < words[i - 1]['s']: words[i]['s'] = round(words[i - 1]['s'] + 0.04, 2)
    if words[i]['e'] < words[i]['s'] + 0.05: words[i]['e'] = round(words[i]['s'] + 0.12, 2)
spk = json.load(open('spk.json')); LAB = np.array(spk['lab']); HOP = spk['hop']
boxes = json.load(open('boxes_s3.json'))
CROP = {'S1': (684, 75, 1432, 1080), 'S2': (292, 96, 1168, 1005)}
# people: mic label -> (camera, face x, face y) in the 1920x1080 source
PEOPLE = {1: ('AVE', 1020, 300), 2: ('093A', 525, 345), 3: ('093A', 1410, 450)}

w = wave.open('au/Left_Audio_Channel_54_16k.wav')
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
E = 20 * np.log10(np.sqrt((x[:len(x)//160*160].reshape(-1, 160)**2).mean(1)) + 1e-3)
THR = np.percentile(E, 30) + 8
loud = np.convolve(E > THR, np.ones(5), 'same') > 0

def quiet_snap(t, back):
    i = int(t * 100); rng = range(i, i - 30, -1) if back else range(i, i + 30)
    for k in rng:
        if 0 <= k < len(loud) and not loud[k]: return k / 100
    return t

def trim_silence(a, b, mingap=0.25, keep=0.08):
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
    return [(p, q) for p, q in out if q - p > 0.12]

def who(t0, t1, prev):
    seg = LAB[int(t0 / HOP):max(int(t0 / HOP) + 1, int(t1 / HOP))]; seg = seg[seg > 0]
    if len(seg) == 0: return prev
    return int(np.bincount(seg, minlength=4)[1:].argmax() + 1)

def s3_box(t):
    bs = np.array([b[1:] for b in boxes if abs(b[0] - t) <= 1.5])
    if len(bs) == 0: return (360, 60, 1320, 1060)
    x0, y0, x1, y1 = np.median(bs, 0)
    return (int(max(0, x0 - 50)), int(max(60, y0)), int(min(1920, x1 + 50)), int(min(1060, y1)))

def norm(s): return re.sub(r"[^a-z0-9']", "", s.lower())
FILLER = {'uh', 'um', 'mhm', 'mm', 'huh'}
FIXW = {'tesco': 'CHESKO', 'stuart': 'STEWART', "stuart's": "STEWART'S", 'tip': 'TIP'}
KEY = {
 '01': 'camera pause seventeen pretended magic hands video blaine hologram tupac eric smith',
 '02': 'eyes knee shorts gap nailed focal drawing pulp richmond chesko chad',
 '03': 'tiger ramos doggie unbelievable nose shocking cheesing breathe suffering alive corgi sad',
 '04': 'dark fucked values last lines structure hold black gray right lighten perfect softened',
 '05': 'fresh healed match depth separation splashes soft gray dark',
 '06': 'elbow screamer stewart rocks koi jumping business clouds wind eye red orange striking',
 '07': 'porter_electric aeconner headphone yawning slippers bathroom shirtless costanza shirt',
}
REPL = {'07': [(('at', 'connor'), '@AECONNER'), (('porter', 'underscore', 'electric'), '@PORTER_ELECTRIC')],
        '02': [(('chad', 'tesco'), 'CHAD CHESKO')]}
DROP = {'07': {'beside', 'yoongi'}}

plan = []
for r in R:
    rid = r['id']; tattoo = r['kind'] == 'tattoo'
    rngs = [dict(r['hook'], hook=True)] + [dict(b, hook=False) for b in r['body']]
    # ---- audio pieces
    spans = []
    for n, g in enumerate(rngs):
        a, b = g['r']
        s0 = quiet_snap(g.get('start_t', words[a]['s'] - 0.10), True); s1 = quiet_snap(g.get('end_t', words[b]['e'] + 0.25), False)
        if (n > 1 and spans[-1]['s0'] <= s0 < spans[-1]['s1'] + 0.4 and not g.get('broll')
                and not spans[-1].get('broll')):
            spans[-1]['s1'] = max(spans[-1]['s1'], s1); spans[-1]['b'] = b; continue
        spans.append(dict(s0=s0, s1=s1, a=a, b=b, n=n, broll=g.get('broll'), faces=g.get('faces', False)))
    pieces = []; frame = 0
    for sp in spans:
        for p, q in trim_silence(sp['s0'], sp['s1']):
            nf = max(1, int(round((q - p) / FR)))
            pieces.append(dict(src0=p, nf=nf, f0=frame, span=sp['n'], broll=sp['broll'], faces=sp['faces'], a=sp['a'], b=sp['b']))
            frame += nf
    NF = frame
    def src_at(f):          # reel frame -> (piece, mic time)
        for p in pieces:
            if p['f0'] <= f < p['f0'] + p['nf']: return p, p['src0'] + (f - p['f0']) * FR
        p = pieces[-1]; return p, p['src0'] + (p['nf'] - 1) * FR
    # ---- reel-time words (for captions + cut snapping)
    rw = []
    for p in pieces:
        p_end = p['src0'] + p['nf'] * FR
        for i in range(p['a'], p['b'] + 1):
            if p['src0'] - 0.05 <= words[i]['s'] < p_end:
                rw.append(dict(i=i, w=words[i]['w'], p=words[i]['p'],
                               s=p['f0'] * FR + max(0, words[i]['s'] - p['src0']),
                               e=p['f0'] * FR + min(p_end, words[i]['e']) - p['src0']))
    starts = sorted(set([round(x['s'] / FR) for x in rw] + [p['f0'] for p in pieces] + [s['n'] for s in []]))
    spanstarts = sorted(set(p['f0'] for k, p in enumerate(pieces) if k == 0 or pieces[k - 1]['span'] != p['span']))
    def pick_cut(f, lo, hi):
        lo, hi = int(f + lo / FR), int(f + hi / FR)
        if lo >= NF - int(0.8 / FR): return NF
        ss = [s for s in spanstarts if lo <= s <= hi]
        if ss: return ss[0]
        cand = [s for s in starts if lo <= s <= hi]
        mid = (lo + hi) / 2
        return min(cand, key=lambda s: abs(s - mid)) if cand else int(mid)
    # ---- shots
    shots = []; f = 0; k = 0; prev_person = 1; zoom_toggle = 0; brk = {}
    while f < NF:
        pc, _ = src_at(f); faces_here = (not tattoo) or pc['faces']
        if k == 0: kind, lo, hi = 'F', 0.7, 1.3                     # change inside the first second
        elif not faces_here: kind, lo, hi = ('T', 2.2, 3.8) if (not shots or shots[-1]['kind'] == 'F') else ('F', 1.6, 2.8)
        else: kind, lo, hi = 'F', 1.7, 3.2
        e = pick_cut(f, lo, hi)
        if NF - e < int(1.0 / FR): e = NF
        if kind == 'T':                       # a tattoo shot never runs into a faces-only stretch
            fs = [q['f0'] for q in pieces if q['faces'] and q['f0'] > f]
            if fs and fs[0] < e: e = fs[0]
        p, t0 = src_at(f); _, t1 = src_at(e - 1)
        sh = dict(f0=f, f1=e, kind=kind)
        if kind == 'F':
            person = who(t0, t1 + FR, prev_person)
            if faces_here and k > 0 and shots and shots[-1].get('person') == person:
                zoom_toggle ^= 1
                if zoom_toggle == 0:                                   # reaction cutaway
                    person = [q for q in (1, 2, 3) if q != person][k % 2]
            sh['person'] = person; sh['zoom'] = 1.0 if (len([s for s in shots if s['kind'] == 'F']) % 2 == 0) else 1.14
            prev_person = person if who(t0, t1 + FR, prev_person) == person else prev_person
        else:
            sh['broll'] = None
            if p['broll']:
                j = brk.get(p['span'], 0); sh['broll'] = p['broll'][j % len(p['broll'])]; brk[p['span']] = j + 1
        shots.append(sh); f = e; k += 1
    # ---- chunks = shots x pieces
    chunks = []
    for sh in shots:
        for p in pieces:
            a = max(sh['f0'], p['f0']); b = min(sh['f1'], p['f0'] + p['nf'])
            if b <= a: continue
            src = p['src0'] + (a - p['f0']) * FR
            c = dict(nf=b - a, src=round(src, 4), kind=sh['kind'])
            if sh['kind'] == 'F':
                cam, fx, fy = PEOPLE[sh['person']]; z = sh['zoom']
                h = 1080 / z; wdt = h * 9 / 16
                x0 = min(max(0, fx - wdt / 2), 1920 - wdt); y0 = min(max(0, fy - 0.30 * h), 1080 - h)
                c.update(cam=cam, crop=[int(wdt) // 2 * 2, int(h) // 2 * 2, int(x0), int(y0)])
            else:
                obs_t = sh['broll'] if sh['broll'] is not None else src
                box = CROP[r['sect']] if r['sect'] != 'S3' else s3_box(obs_t)
                d = (sh['f1'] - sh['f0'])
                c.update(obs=round(obs_t, 3), still=sh['broll'] is not None, box=list(box),
                         z0=round(1 + 0.06 * (a - sh['f0']) / d, 4), z1=round(1 + 0.06 * (b - sh['f0']) / d, 4))
            chunks.append(c)
    # ---- captions
    keys = set(norm(k) for k in KEY.get(rid, '').split())
    toks = []; i = 0
    while i < len(rw):
        rep = None
        for pat, out in REPL.get(rid, []):
            if tuple(norm(rw[j]['w']) for j in range(i, min(len(rw), i + len(pat)))) == pat: rep = (pat, out); break
        if rep:
            toks.append(dict(t=rep[1], s=rw[i]['s'], e=rw[i + len(rep[0]) - 1]['e'], k=True, p=''))
            i += len(rep[0]); continue
        tk = norm(rw[i]['w'])
        if tk in FILLER or tk in DROP.get(rid, set()): i += 1; continue
        txt = FIXW.get(tk, rw[i]['w'].upper())
        toks.append(dict(t=txt.upper(), s=rw[i]['s'], e=rw[i]['e'], k=tk in keys, p=rw[i]['p'])); i += 1
    cap = []; cur = []
    for j, tk in enumerate(toks):
        cur.append(tk); nxt = toks[j + 1] if j + 1 < len(toks) else None
        chars = sum(len(c['t']) + 1 for c in cur)
        if (nxt is None or len(cur) >= 3 or (tk['p'] and tk['p'][-1] in '.?!,') or nxt['s'] - tk['e'] > 0.3
                or chars + len(nxt['t']) > 14):
            cap.append(dict(s=cur[0]['s'], e=cur[-1]['e'], toks=cur)); cur = []
    cap.sort(key=lambda c: c['s'])
    plan.append(dict(id=rid, slug=r['slug'], kind=r['kind'], handle=r.get('handle'), title=r['title'],
                     pieces=pieces, chunks=chunks, shots=shots, frames=NF, dur=round(NF * FR, 2), cap=cap))
    nT = sum(1 for s in shots if s['kind'] == 'T')
    print(rid, r['slug'], f"{NF*FR:5.1f}s", 'shots', len(shots), f"({nT} tattoo)", 'cuts/min', round((len(shots) - 1) / (NF * FR) * 60, 1),
          'first cut', round(shots[1]['f0'] * FR, 2) if len(shots) > 1 else None, 'chunks', len(chunks))
json.dump(plan, open('plan2.json', 'w'), default=float)
