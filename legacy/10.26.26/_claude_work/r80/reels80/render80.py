"""R80 reels renderer (Mac shell) — R78 v3 renderer with R79 sources. usage: python3 render79.py 01 02 ... | --mux 01 ..."""
import json, os, sys, subprocess, time
H = '/tmp/reels80'
REL = os.path.expanduser('~/mnt/NLJBS Drive/WORKING SHOP TALM FILES/10.26.26/RECORDING 2')
OUTD = os.path.join(H, 'out')
SRC = {'AVE': f'{REL}/AVE14202.MP4', '093A': f'{REL}/093A6724.MP4', 'OBS': f'{REL}/2026-10-26 18-33-39.mp4'}
WAV = f'{H}/R80_mix48k.wav'   # Mic 1 Porter + Mic 2 AC + Mic 3 Jake, mic time 0 = sample 0
OFF = {'AVE': 40.9585, '093A': 61.856, 'OBS': 64.4875}  # source time = mic time + OFF
FR = 1001 / 30000
WARM = 'colorbalance=rm=0.03:bm=-0.03:rh=0.02:bh=-0.02'
GRADE = {'AVE': f'eq=contrast=1.22:brightness=0.05:gamma=1.22:saturation=1.45,{WARM}',
         '093A': f'eq=contrast=1.32:brightness=0.03:gamma=1.38:saturation=1.42,{WARM}'}
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', '30000/1001', '-an']
T3 = f'{H}/tmp'; os.makedirs(T3, exist_ok=True); os.makedirs(OUTD, exist_ok=True)
plan = {p['id']: p for p in json.load(open(f'{H}/plan80r.json'))}
def ev(n): return int(n) // 2 * 2
def run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: print('FAIL', what, r.stderr[-1200:]); sys.exit(1)

def face_shot(s, fn):
    fx, fy = s['face']; base = s['base']
    h = 1080 / base; w = h * 9 / 16
    x0 = min(max(0, fx - w / 2), 1920 - w); y0 = min(max(0, fy - 0.30 * h), 1080 - h)
    ax = (fx - x0) / w; ay = min(0.45, (fy - y0) / h)
    total = sum(p['nf'] for p in s['parts']); done = 0; parts = []
    for k, p in enumerate(s['parts']):
        za = 1 + 0.05 * done / total; zb = 1 + 0.05 * (done + p['nf']) / total; D = p['nf'] * FR
        Z = f"({za:.5f}+({zb - za:.5f})*t/{D:.4f})"
        vf = (f"setpts=PTS-STARTPTS,crop={ev(w)}:{ev(h)}:{int(x0)}:{int(y0)},"
              f"scale=w='ceil(1080*{Z}/2)*2':h='ceil(1920*{Z}/2)*2':eval=frame:flags=bicubic,"
              f"crop=1080:1920:x='(iw-1080)*{ax:.4f}':y='(ih-1920)*{ay:.4f}',{GRADE[s['cam']]},format=yuv420p")
        pf = f"{fn}.p{k}.mp4"
        run(['ffmpeg', '-v', 'error', '-y', '-ss', f"{p['src'] + OFF[s['cam']]:.3f}", '-i', SRC[s['cam']], '-vf', vf,
             '-frames:v', str(p['nf'])] + ENC + [pf], 'face part')
        parts.append(pf); done += p['nf']
    if len(parts) == 1: os.replace(parts[0], fn); return
    lst = fn + '.txt'
    with open(lst, 'w') as f:
        for pf in parts: f.write(f"file '{pf}'\n")
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', fn], 'face concat')
    for pf in parts: os.remove(pf)

def tat_shot(s, fn):
    x0, y0, x1, y1 = s['box']; bw, bh = x1 - x0, y1 - y0
    sc = min(1080 / bw, 1300 / bh); fw, fh = ev(bw * sc), ev(bh * sc)
    nf = s['f1'] - s['f0'] + s['xin']; D = nf * FR
    Z = f"({s['z0']}+({s['z1']}-{s['z0']})*t/{D:.4f})"
    pre = "setpts=PTS-STARTPTS,fps=30000/1001"
    if s['still']: pre += ",trim=end_frame=1,loop=loop=-1:size=1,setpts=N/(30000/1001)/TB"
    fc = (f"[0:v]{pre},crop={bw}:{bh}:{x0}:{y0},split[a][b];"
          f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.28:saturation=0.9[bg];"
          f"[b]scale=w='ceil({fw}*{Z}/2)*2':h='ceil({fh}*{Z}/2)*2':eval=frame:flags=bicubic,crop={fw}:{fh}[fg];"
          f"[bg][fg]overlay=(W-w)/2:880-h/2,format=yuv420p[v]")
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f"{s['obs'] + OFF['OBS']:.3f}", '-i', SRC['OBS'],
         '-filter_complex', fc, '-map', '[v]', '-frames:v', str(nf)] + ENC + [fn], 'tattoo shot')

def assemble(rid, files):
    P = plan[rid]; S = P['shots']
    inputs = []; fl = []
    for k, fn in enumerate(files):
        inputs += ['-i', fn]; fl.append(f"[{k}:v]settb=AVTB,fps=30000/1001,format=yuv420p[s{k}]")
    cur = 's0'; dur = (S[0]['f1'] - S[0]['f0']) * FR
    for k in range(1, len(S)):
        d = (S[k]['f1'] - S[k]['f0']) * FR
        if S[k]['xin']:
            x = S[k]['xin'] * FR
            fl.append(f"[{cur}][s{k}]xfade=transition=fade:duration={x:.4f}:offset={dur - x:.4f},settb=AVTB,fps=30000/1001[c{k}]")
        else:
            fl.append(f"[{cur}][s{k}]concat=n=2:v=1:a=0,settb=AVTB,fps=30000/1001[c{k}]")
        cur = f"c{k}"; dur += d
    aparts = []
    for i, p in enumerate(P['pieces']):
        d = p['nf'] * FR
        fl.append(f"[{len(files)}:a]atrim=start={p['src0']:.4f}:duration={d:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.006,afade=t=out:st={d-0.006:.4f}:d=0.006[a{i}]")
        aparts.append(f'[a{i}]')
    fl.append(f"{''.join(aparts)}concat=n={len(aparts)}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a]")
    fl.append(f"[{cur}]ass={H}/R80_{rid}.ass:fontsdir={H}/fonts[v]")
    out = f"{T3}/R80_{rid}_{P['slug']}_pre.mp4"
    with open(f'{T3}/{rid}_graph.txt', 'w') as f: f.write(';\n'.join(fl))
    run(['ffmpeg', '-v', 'error', '-y'] + inputs + ['-i', WAV, '-filter_complex_script', f'{T3}/{rid}_graph.txt',
         '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-map_metadata', '-1', '-map_chapters', '-1',
         '-write_tmcd', '0', '-shortest', out], 'assemble')
    # loudness: one-pass loudnorm lands ~2-3 dB under target -> measure, then gain + true-peak limit to -14 LUFS
    r = subprocess.run(['ffmpeg', '-nostdin', '-i', out, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True)
    I = float([l for l in r.stderr.splitlines() if l.strip().startswith('I:')][-1].split()[1])
    fin = f"{OUTD}/R80_{rid}_{P['slug']}.mp4"
    run(['ffmpeg', '-v', 'error', '-y', '-i', out, '-c:v', 'copy', '-af', f'volume={-14 - I:.2f}dB,alimiter=limit=0.84:level=false',
         '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', fin], 'loudness')
    os.remove(out)
    return fin

args = sys.argv[1:]; only_mux = args and args[0] == '--mux'
for rid in (args[1:] if only_mux else args):
    t0 = time.time(); P = plan[rid]; files = []
    for k, s in enumerate(P['shots']):
        fn = f"{T3}/{rid}_{k:03d}.mp4"; files.append(fn)
        if only_mux or os.path.exists(fn + '.ok'): continue
        (face_shot if s['kind'] == 'F' else tat_shot)(s, fn)
        open(fn + '.ok', 'w').close()
    out = assemble(rid, files)
    print(rid, 'shots', len(files), 'wrote', os.path.basename(out), f'{time.time()-t0:.0f}s')
