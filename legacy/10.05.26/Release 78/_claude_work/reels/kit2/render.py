"""R78 reels renderer (runs on the Mac's shell). usage: python3 render.py 01 02 ...   (ids from plan.json)
chunks cached in ~/reels/tmp (delete tmp/<id>_* to rebuild a reel's pieces)."""
import json, os, sys, subprocess, time
H = os.path.expanduser('~/reels')
REL = os.path.expanduser('~/mnt/WORKING SHOP TALM FILES/10.05.26/Release 78')
OUTD = os.path.join(REL, 'R78_REELS')
SRC = {'AVE': f'{REL}/AVE11879.MP4', '093A': f'{REL}/093A2069.MP4', 'OBS': f'{REL}/2026-10-05 20-27-08.mp4'}
WAV = f'{REL}/Left Audio Channel#54.wav'
OFF = {'AVE': 10.170, '093A': 36.675, 'OBS': -17.701}
FR = 1001 / 30000
GRADE = {'AVE': 'eq=contrast=1.22:brightness=0.05:gamma=1.22:saturation=1.4',
         '093A': 'eq=contrast=1.32:brightness=0.03:gamma=1.38:saturation=1.38'}
# cam crops (x,y,w,h in the 1920x1080 frame)
TAT_CAM = {'AVE': (360, 40, 1320, 807), '093A': (76, 0, 1767, 1080)}     # -> 1080x660
TALK_CAM = {'AVE': (430, 40, 1180, 907), '093A': (258, 0, 1404, 1080)}   # -> 1080x830
os.makedirs(f'{H}/tmp', exist_ok=True); os.makedirs(OUTD, exist_ok=True)
plan = {p['id']: p for p in json.load(open(f'{H}/plan.json'))}
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', '30000/1001', '-an']
def ev(n): return int(n) // 2 * 2

def chunks(P):
    """flatten pieces -> frame-quantized visual chunks"""
    out = []
    for p in P['pieces']:
        f0 = 0
        subs = p['subs']
        for si, s in enumerate(subs):
            cams = s.get('cams') or [(s['src0'], s['src1'], None)]
            for ci, (a, b, cam) in enumerate(cams):
                last = si == len(subs) - 1 and ci == len(cams) - 1
                f1 = p['nf'] if last else min(p['nf'], int(round((b - p['src0']) / FR)))
                if f1 > f0:
                    out.append(dict(t=p['src0'] + f0 * FR, nf=f1 - f0, box=s.get('box'), cam=cam))
                f0 = max(f0, f1)
    return out

def tattoo_chunk(c, fn):
    bx0, by0, bx1, by1 = c['box']; bw, bh = bx1 - bx0, by1 - by0
    s = min(1032 / bw, 952 / bh); fw, fh = ev(bw * s), ev(bh * s)
    cx, cy, cw, ch = TAT_CAM[c['cam']]
    fc = (f"[0:v]fps=30000/1001,crop={bw}:{bh}:{bx0}:{by0},split[a][b];"
          f"[a]scale=1080:1000:force_original_aspect_ratio=increase,crop=1080:1000,gblur=sigma=30,eq=brightness=-0.20:saturation=0.85[bg];"
          f"[b]scale={fw}:{fh},pad={fw+12}:{fh+12}:6:6:white[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2[top];"
          f"[1:v]crop={cw}:{ch}:{cx}:{cy},scale=1080:660,{GRADE[c['cam']]},format=yuv420p[cam];"
          f"color=black:s=1080x1920:r=30000/1001[base];[base][top]overlay=0:0[t1];[t1][cam]overlay=0:1260[t2];"
          f"[t2]drawbox=x=0:y=1000:w=1080:h=6:color=white:t=fill,drawbox=x=0:y=1254:w=1080:h=6:color=white:t=fill,format=yuv420p[v]")
    cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', f"{c['t'] + OFF['OBS']:.3f}", '-i', SRC['OBS'],
           '-ss', f"{c['t'] + OFF[c['cam']]:.3f}", '-i', SRC[c['cam']], '-filter_complex', fc, '-map', '[v]',
           '-frames:v', str(c['nf'])] + ENC + [fn]
    return cmd

def talk_chunk(c, fn):
    a = TALK_CAM['AVE']; g = TALK_CAM['093A']
    fc = (f"[0:v]crop={a[2]}:{a[3]}:{a[0]}:{a[1]},scale=1080:830,{GRADE['AVE']},format=yuv420p[n];"
          f"[1:v]crop={g[2]}:{g[3]}:{g[0]}:{g[1]},scale=1080:830,{GRADE['093A']},format=yuv420p[g];"
          f"color=black:s=1080x1920:r=30000/1001[base];[base][n]overlay=0:0[t1];[t1][g]overlay=0:1090[t2];"
          f"[t2]drawbox=x=0:y=830:w=1080:h=6:color=white:t=fill,drawbox=x=0:y=1084:w=1080:h=6:color=white:t=fill,format=yuv420p[v]")
    return ['ffmpeg', '-v', 'error', '-y', '-ss', f"{c['t'] + OFF['AVE']:.3f}", '-i', SRC['AVE'],
            '-ss', f"{c['t'] + OFF['093A']:.3f}", '-i', SRC['093A'], '-filter_complex', fc, '-map', '[v]',
            '-frames:v', str(c['nf'])] + ENC + [fn]

for rid in sys.argv[1:]:
    t0 = time.time(); P = plan[rid]; CH = chunks(P); files = []
    for k, c in enumerate(CH):
        fn = f"{H}/tmp/{rid}_{k:03d}.mp4"; files.append(fn)
        if os.path.exists(fn + '.ok'): continue
        cmd = tattoo_chunk(c, fn) if P['kind'] == 'tattoo' else talk_chunk(c, fn)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode: print('chunk fail', rid, k, r.stderr[-800:]); sys.exit(1)
        open(fn + '.ok', 'w').close()
    with open(f'{H}/tmp/{rid}_list.txt', 'w') as f:
        for fn in files: f.write(f"file '{fn}'\n")
    # audio: same source ranges off the clean mic mix, 8 ms fades at every join
    parts = []; fl = []
    for i, p in enumerate(P['pieces']):
        d = p['nf'] * FR
        fl.append(f"[1:a]atrim=start={p['src0']:.4f}:duration={d:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={d-0.008:.4f}:d=0.008[a{i}]")
        parts.append(f'[a{i}]')
    fc = ';'.join(fl) + f";{''.join(parts)}concat=n={len(parts)}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a];" \
         f"[0:v]ass={H}/R78_{rid}.ass:fontsdir={H}/fonts[v]"
    out = f"{OUTD}/R78_{rid}_{P['slug']}.mp4"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{H}/tmp/{rid}_list.txt', '-i', WAV,
                        '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-map_metadata', '-1', '-map_chapters', '-1', '-write_tmcd', '0', '-shortest', out],
                       capture_output=True, text=True)
    if r.returncode: print('final fail', rid, r.stderr[-1500:]); sys.exit(1)
    print(rid, 'chunks', len(CH), 'wrote', os.path.basename(out), f'{time.time()-t0:.0f}s')
