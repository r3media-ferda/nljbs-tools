"""R78 reels v2 renderer (Mac shell). usage: python3 render2.py 01 02 ... | --mux 01 02 (re-mux captions only)
Every chunk is built from ONE input with setpts reset, so frame 1 is always real picture (no black flash)."""
import json, os, sys, subprocess, time
H = os.path.expanduser('~/reels')
REL = os.path.expanduser('~/mnt/WORKING SHOP TALM FILES/10.05.26/Release 78')
OUTD = os.path.join(REL, 'R78_REELS_v2')
SRC = {'AVE': f'{REL}/AVE11879.MP4', '093A': f'{REL}/093A2069.MP4', 'OBS': f'{REL}/2026-10-05 20-27-08.mp4'}
WAV = f'{REL}/Left Audio Channel#54.wav'
OFF = {'AVE': 10.170, '093A': 36.675, 'OBS': -17.701}
FR = 1001 / 30000
WARM = 'colorbalance=rm=0.03:bm=-0.03:rh=0.02:bh=-0.02'
GRADE = {'AVE': f'eq=contrast=1.22:brightness=0.05:gamma=1.22:saturation=1.45,{WARM}',
         '093A': f'eq=contrast=1.32:brightness=0.03:gamma=1.38:saturation=1.42,{WARM}'}
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '30000/1001', '-an']
os.makedirs(f'{H}/tmp2', exist_ok=True); os.makedirs(OUTD, exist_ok=True)
plan = {p['id']: p for p in json.load(open(f'{H}/plan2.json'))}
def ev(n): return int(n) // 2 * 2

def face_chunk(c, fn):
    w, h, x, y = c['crop']
    vf = f"setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale=1080:1920:flags=lanczos,{GRADE[c['cam']]},format=yuv420p"
    return ['ffmpeg', '-v', 'error', '-y', '-ss', f"{c['src'] + OFF[c['cam']]:.3f}", '-i', SRC[c['cam']],
            '-vf', vf, '-frames:v', str(c['nf'])] + ENC + [fn]

def tat_chunk(c, fn):
    x0, y0, x1, y1 = c['box']; bw, bh = x1 - x0, y1 - y0
    s = min(1080 / bw, 1300 / bh); fw, fh = ev(bw * s), ev(bh * s)
    D = c['nf'] * FR; z0, z1 = c['z0'], c['z1']
    zoom = f"({z0}+({z1}-{z0})*t/{D:.4f})"
    pre = "setpts=PTS-STARTPTS,fps=30000/1001"
    if c['still']: pre += ",trim=end_frame=1,loop=loop=-1:size=1,setpts=N/(30000/1001)/TB"
    fc = (f"[0:v]{pre},crop={bw}:{bh}:{x0}:{y0},split[a][b];"
          f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.28:saturation=0.9[bg];"
          f"[b]scale=w='ceil({fw}*{zoom}/2)*2':h='ceil({fh}*{zoom}/2)*2':eval=frame,crop={fw}:{fh}[fg];"
          f"[bg][fg]overlay=(W-w)/2:880-h/2,format=yuv420p[v]")
    return ['ffmpeg', '-v', 'error', '-y', '-ss', f"{c['obs'] + OFF['OBS']:.3f}", '-i', SRC['OBS'],
            '-filter_complex', fc, '-map', '[v]', '-frames:v', str(c['nf'])] + ENC + [fn]

def mux(rid):
    P = plan[rid]; parts = []; fl = []
    for i, p in enumerate(P['pieces']):
        d = p['nf'] * FR
        fl.append(f"[1:a]atrim=start={p['src0']:.4f}:duration={d:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.006,afade=t=out:st={d-0.006:.4f}:d=0.006[a{i}]")
        parts.append(f'[a{i}]')
    fc = ';'.join(fl) + f";{''.join(parts)}concat=n={len(parts)}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a];" \
         f"[0:v]ass={H}/R78v2_{rid}.ass:fontsdir={H}/fonts[v]"
    out = f"{OUTD}/R78_{rid}_{P['slug']}.mp4"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{H}/tmp2/{rid}_list.txt', '-i', WAV,
                        '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-map_metadata', '-1',
                        '-map_chapters', '-1', '-write_tmcd', '0', '-shortest', out], capture_output=True, text=True)
    if r.returncode: print('mux fail', rid, r.stderr[-1500:]); sys.exit(1)
    return out

args = sys.argv[1:]; only_mux = args and args[0] == '--mux'
for rid in (args[1:] if only_mux else args):
    t0 = time.time(); P = plan[rid]; files = []
    for k, c in enumerate(P['chunks']):
        fn = f"{H}/tmp2/{rid}_{k:03d}.mp4"; files.append(fn)
        if only_mux or os.path.exists(fn + '.ok'): continue
        cmd = face_chunk(c, fn) if c['kind'] == 'F' else tat_chunk(c, fn)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode: print('chunk fail', rid, k, c, r.stderr[-800:]); sys.exit(1)
        open(fn + '.ok', 'w').close()
    with open(f'{H}/tmp2/{rid}_list.txt', 'w') as f:
        for fn in files: f.write(f"file '{fn}'\n")
    out = mux(rid)
    print(rid, 'chunks', len(files), 'wrote', os.path.basename(out), f'{time.time()-t0:.0f}s')
