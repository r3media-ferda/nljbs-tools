"""`nljbs reels <reels.yaml> [ids...]`: R78 v3 reels (handoff section 10), ported from legacy r80/reels80.

plan  : resolve phrase ranges to ASR words, trim gaps > 0.30 s between words, speaker turns, shots
        (talk: speaker tight every 2.4-3.6 s; tattoo: cold open on the face, then tattoo <-> speaker),
        YuNet face per shot, tattoo shots clamped to the reel's post (OBS live states only, else a still)
ass   : Black Takora captions on the word, 1-3 words/card, red keywords at y=1170, @HANDLE over tattoo shots
render: per-shot ffmpeg from ONE input with setpts reset; faces get the camera's SHOPTALK LUT + reel boost;
        6-frame dissolves on tattoo boundaries; mic mix -> loudnorm -> measured gain + limiter to -14 LUFS
verify: re-ASR vs caption cards, luma-dip scan, loudness/true peak, 1 fps contact sheet per reel
Renders to ~/nljbs-work/<rec>/R<NN>_REELS; `--deliver` copies to the recording folder (new names only).
"""
import csv
import datetime as dt
import filecmp
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

from . import media

FPS = 30000 / 1001
FR = 1 / FPS
ROOT = Path(__file__).resolve().parent.parent


def fr(t): return int(round(t * FPS))
def ev(n): return int(n) // 2 * 2
def norm(s): return re.sub(r"[^a-z0-9'$]", "", s.lower())


class Ctx:
    def __init__(self, reels_yaml):
        self.R = yaml.safe_load(Path(reels_yaml).read_text())
        self.E = yaml.safe_load((ROOT / self.R["edit"]).read_text())
        self.ep = yaml.safe_load(Path(os.path.expanduser(self.E["episode"])).read_text())
        self.work = Path(self.ep["work_dir"]); self.rec = Path(self.ep["recording_folder"])
        self.rel = self.E["release"]
        self.out = self.work / f"R{self.rel}_REELS"; self.tmp = self.work / "reels_tmp"
        self.out.mkdir(exist_ok=True); self.tmp.mkdir(exist_ok=True)
        rep = yaml.safe_load((self.work / "sync_report.yaml").read_text())
        self.SRC, self.OFF = {}, {}
        for c in self.ep["cameras"]:
            k = {"ave": "AVE", "093a": "093A", "wide": "C"}[c["kind"]]
            if self.E.get("two_shot_cam") == "093a":       # same role keys as the switcher
                k = {"AVE": "093A", "093A": "AVE"}.get(k, k)
            self.SRC[k] = c["file"]; self.OFF[k] = -rep[Path(c["file"]).name]["offset_s"]   # source t = mic t + OFF
        self.SRC["OBS"] = self.ep["obs"][0]; self.OFF["OBS"] = -rep[Path(self.ep["obs"][0]).name]["offset_s"]
        names = [m["who"].upper() for m in self.ep["mics"]]
        self.CODE = {n: ("AC" if n == "AC" else n[0]) for n in names}          # PORTER->P, AC->AC, JAKE->J
        self.CAM = {self.CODE[n]: self.E["cast"][n]["cam"] for n in names}
        self.WHO = {v: k for k, v in self.CODE.items()}
        self.DUR = {k: media.summarize(p)["duration"] for k, p in self.SRC.items()}
        self.DEF = {self.CODE[n]: self.E["faces"][self.E["cast"][n]["cam"]][n] for n in names}
        g = self.E["grade"]["cameras"]; ld = self.work / "luts"
        self.GRADE = {}
        for stem, spec in g.items():
            k = next(k for k, p in self.SRC.items() if Path(p).stem == stem)
            self.GRADE[k] = f"lut3d=file='{ld / ('SHOPTALK_' + spec['label'] + '.cube')}':interp=tetrahedral,{self.R['grade_boost']}"
        raw = json.loads((self.work / "words.json").read_text())
        self.W = [dict(w=w["w"], t=w["t0"], end=w["t1"], s=self.CODE[w["spk"]]) for w in raw]
        hold = set(self.E.get("hold_runs", []))
        runs = json.loads((self.work / "screen.json").read_text())
        for r in runs: r["box"] = (self.E.get("run_boxes") or {}).get(r["k"], r["box"])   # hand-measured boxes win
        diff = np.load(self.work / "obs_diff10.npy")
        self.LIVE = []                                            # (OBS a, OBS b, image box)
        prev = None
        for r in runs:
            # tattoo video playing: box measured inside the gap (screen.py), not the previous layout's box
            gbox = (self.E.get("gap_boxes") or {}).get(r["k"]) or r.get("gap_box") or (prev and prev["box"])
            measured = (self.E.get("gap_boxes") or {}).get(r["k"]) or r.get("gap_box")
            if prev and gbox and (measured or prev["k"] not in hold) and r["a"] - prev["b"] >= 3.0:
                gseg = diff[int(prev["b"] * 10):int(r["a"] * 10)]
                if len(gseg) and np.median(gseg) < 4.0:
                    self.LIVE.append((prev["b"], r["a"], gbox))
            if r["k"] not in hold and r["box"]:
                self.LIVE.append((r["a"], r["b"], r["box"]))
            prev = r
        for xa, xb in self.R.get("exclude_obs", []) or []:      # e.g. profile grids scrolling: never a tattoo shot
            self.LIVE = [(a, b, box) for a, b, box in self.LIVE if b <= xa or a >= xb]
        self.det = cv2.FaceDetectorYN.create(str(media.WORK_ROOT / "models" / "yunet.onnx"), "", (1920, 1080), 0.6)
        self.static = self._static_faces()

    def _raw_faces(self, cam, t):
        raw = subprocess.run([media.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", self.SRC[cam], "-frames:v", "1",
                              "-vf", "scale=1920:1080", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        if len(raw) < 1920 * 1080 * 3: return []
        _, fs = self.det.detect(np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3))
        return [] if fs is None else [(x + w / 2, y + h / 2, w) for x, y, w, h, *_ in fs]

    def _static_faces(self):
        """Faces in the wall art: detections that sit in the same spot (+-6 px) in most of 8 frames across the take."""
        cache = self.tmp / "static_faces.json"
        if cache.exists(): return {k: [tuple(p) for p in v] for k, v in json.loads(cache.read_text()).items()}
        out = {}
        for cam in {c for c in self.CAM.values()}:
            dur = media.summarize(self.SRC[cam])["duration"]
            hits = [self._raw_faces(cam, dur * q) for q in np.linspace(0.08, 0.92, 8)]
            pts = [f[:2] for fr_ in hits for f in fr_]
            out[cam] = [p for p in pts if sum(any(abs(p[0] - q[0]) < 6 and abs(p[1] - q[1]) < 6 for q in [f[:2] for f in fr_])
                                              for fr_ in hits) >= 5]
            out[cam] = [list(p) for i, p in enumerate(out[cam]) if all(abs(p[0] - q[0]) > 6 or abs(p[1] - q[1]) > 6 for q in out[cam][:i])]
        cache.write_text(json.dumps({k: [list(map(float, p)) for p in v] for k, v in out.items()}))
        return out

    def boxat(self, o):
        for a, b, box in self.LIVE:
            if a <= o < b: return list(box)
        return None

    def fits(self, o, d):
        return any(a <= o and o + d <= b for a, b, _ in self.LIVE)

    def face_at(self, who, mic_t):
        cam = self.CAM[who]; t = mic_t + self.OFF[cam]; dx, dy = self.DEF[who]
        wall = self.static.get(cam, [])
        c = [f for f in self._raw_faces(cam, t) if f[2] > 70 and abs(f[0] - dx) < 380
             and not any(abs(f[0] - p[0]) < 12 and abs(f[1] - p[1]) < 12 for p in wall)]
        if not c: return None
        f = max(c, key=lambda f: f[2]); return (f[0], f[1])

    def face_for(self, who, times):
        """Face centre for a whole shot: median of detections at several times (people lean and turn)."""
        hits = [h for h in (self.face_at(who, t) for t in times) if h]
        if not hits: return list(self.DEF[who])
        return [int(np.median([h[0] for h in hits])), int(np.median([h[1] for h in hits]))]


# ------------------------------------------------------------------ plan (port of plan80r.py)
def plan(C, S):
    W = C.W
    rr = []
    for t0, fw, t1, lw in S["ranges"]:
        ci = [k for k, w in enumerate(W) if abs(w["t"] - t0) < 2.5 and norm(w["w"]).startswith(norm(str(fw)))]
        cj = [k for k, w in enumerate(W) if abs(w["t"] - t1) < 2.5 and norm(w["w"]).startswith(norm(str(lw)))]
        if not ci or not cj: raise SystemExit(f"resolve fail {S['id']} {fw}@{t0} / {lw}@{t1}")
        i = min(ci, key=lambda k: abs(W[k]["t"] - t0)); j = min(cj, key=lambda k: abs(W[k]["t"] - t1))
        assert j >= i, (S["id"], fw, lw); rr.append((i, j))
    pieces = []
    for i, j in rr:
        st = max(W[i]["t"] - 0.08, (W[i - 1]["end"] + 0.02) if i > 0 else 0)
        segs, cur = [], st
        for k in range(i, j):
            if W[k + 1]["t"] - W[k]["end"] > S.get("gap", 0.30):      # longer pauses get cut; `gap:` lets one breathe
                e = min(max(W[k]["end"] + 0.08, W[k]["t"] + 0.35), W[k + 1]["t"] - 0.08); s2 = W[k + 1]["t"] - 0.08
                if s2 - e > 0.15: segs.append((cur, e, i, k)); cur = s2; i = k + 1
        e = min(W[j]["end"] + 0.08, (W[j + 1]["t"] - 0.03) if j + 1 < len(W) else W[j]["end"] + 0.08)
        segs.append((cur, e, i, j)); pieces += segs
    P, f = [], 0
    for a, b, i, j in pieces:
        nf = fr(b - a); P.append(dict(src0=round(a, 4), nf=nf, f0=f, i=i, j=j)); f += nf
    NF = f
    RW = []
    for pi, p in enumerate(P):
        for k in range(p["i"], p["j"] + 1):
            w = W[k]; rt = p["f0"] * FR + (w["t"] - p["src0"])
            re_ = p["f0"] * FR + (min(w["end"], p["src0"] + p["nf"] * FR) - p["src0"])
            RW.append(dict(w=w["w"], s=w["s"], rt=max(rt, p["f0"] * FR), re=re_, piece=pi))
    spk = [RW[0]["s"]] * NF
    for k, w in enumerate(RW):
        a = fr(w["rt"]); b = fr(RW[k + 1]["rt"]) if k + 1 < len(RW) else NF
        for x in range(max(0, a), min(NF, b)): spk[x] = w["s"]
    turns = []
    for x, s in enumerate(spk):
        if turns and turns[-1][2] == s: turns[-1][1] = x + 1
        else: turns.append([x, x + 1, s])
    ch = True
    while ch:
        ch = False
        for k, t in enumerate(turns):
            if t[1] - t[0] < 18 and len(turns) > 1:
                if k > 0: turns[k - 1][1] = t[1]
                else: turns[1][0] = t[0]
                turns.pop(k); ch = True; break
        m = []
        for t in turns:
            if m and m[-1][2] == t[2]: m[-1][1] = t[1]
            else: m.append(t)
        turns = m

    def spk_at(x):
        for a, b, s in turns:
            if a <= x < b: return s
        return turns[-1][2]

    def next_change(x):
        for a, b, s in turns:
            if a <= x < b: return b
        return NF
    PB = set(p["f0"] for p in P[1:]); ONS = sorted(set(fr(w["rt"]) for w in RW))

    def pick(x, lo, hi, target):
        lo = x + fr(lo); hi = min(NF, x + fr(hi)); tg = x + fr(target)
        if hi >= NF - fr(0.5): return min(hi, NF) if NF - x > fr(hi - x) else NF
        c = [b for b in PB if lo <= b <= hi]
        if c: return min(c, key=lambda b: abs(b - tg))
        c = [o for o in ONS if lo <= o <= hi]
        if c: return min(c, key=lambda o: abs(o - tg))
        return min(hi, max(lo, tg))
    shots, x = [], 0
    if S["kind"] == "talk":
        e = pick(x, 0.7, 1.3, 1.0); e = min(e, next_change(x)) if next_change(x) > fr(0.5) else e
        shots.append(dict(f0=0, f1=e, kind="F", who=spk_at(0))); x = e
        while x < NF:
            nc = next_change(x); rem = nc - x
            lo, hi, tg = S.get("talk_hold", (2.4, 3.6, 3.0))      # `talk_hold:` longer holds = calmer pacing
            e = nc if rem <= fr(hi) else pick(x, lo, hi, tg)
            shots.append(dict(f0=x, f1=e, kind="F", who=spk_at(x))); x = e
    else:
        e = pick(x, 0.7, 1.3, 1.0); shots.append(dict(f0=0, f1=e, kind="F", who=spk_at(0))); x = e; nxt = "T"
        between = fr(S.get("face_between", 0))        # `face_between:` seconds of faces before the next post shot
        while x < NF:
            if nxt == "T":
                e = pick(x, 2.2, 3.6, 3.0); shots.append(dict(f0=x, f1=e, kind="T")); nxt = "F"; since = 0
            else:
                nc = next_change(x)
                e = nc if fr(1.0) <= nc - x <= fr(2.6) else pick(x, 1.6, 2.6, 2.2)
                if nc - x < fr(1.0) and nc < NF: e = max(nc, x + fr(0.6))
                shots.append(dict(f0=x, f1=e, kind="F", who=spk_at(x))); since += e - x
                nxt = "T" if since >= between else "F"
            x = e
    sh_ = []
    for s in shots:
        if s["f1"] - s["f0"] < 15 and sh_: sh_[-1]["f1"] = s["f1"]
        else: sh_.append(s)
    shots = sh_

    def src_at(x):
        for p in P:
            if p["f0"] <= x < p["f0"] + p["nf"]: return p["src0"] + (x - p["f0"]) * FR
        return P[-1]["src0"] + P[-1]["nf"] * FR

    def parts(a, b):
        o, x = [], a
        while x < b:
            p = next(p for p in P if p["f0"] <= x < p["f0"] + p["nf"]); e = min(b, p["f0"] + p["nf"])
            o.append(dict(src=round(src_at(x), 4), nf=e - x)); x = e
        return o
    z = 1.0; res = []; lastbase = {}; prevwho = None
    CL = S.get("clamp", (0, 1e9)); OO = C.OFF["OBS"]
    # Hand-picked clean views (OBS seconds) - whole post on screen, no browser zoom. Shots walk through them in
    # order so consecutive tattoo shots show different stable views of the same piece.
    pool = [tuple(p) for p in S.get("pool", [])]; pi_, pt = 0, (pool[0][0] + 0.3 if pool else None)
    PUSH, ZMAX = S.get("push", 0.010), S.get("push_max", 1.08)
    for k, s in enumerate(shots):
        xin = 6 if k > 0 and (s["kind"] == "T" or shots[k - 1]["kind"] == "T") else 0
        if s["kind"] == "F":
            cam = C.CAM[s["who"]]; base = 1.0
            if prevwho == s["who"]: base = 1.18 if lastbase.get(s["who"], 1.0) == 1.0 else 1.0
            lastbase[s["who"]] = base; prevwho = s["who"]
            pp = parts(s["f0"], s["f1"])
            if xin: pp = [dict(src=round(pp[0]["src"] - xin * FR, 4), nf=xin)] + pp
            # never render outside what the camera recorded (R81 01: AVE rolled at mic 30.0 s, seeks before
            # that clamp to frame 0 and the shot freezes)
            for p in pp:
                a_src = p["src"] + C.OFF[cam]; b_src = a_src + p["nf"] * FR
                if a_src < 0 or b_src > C.DUR[cam]:
                    raise SystemExit(f"reel {S['id']}: {C.WHO[s['who']]} on {cam} at mic {p['src']:.2f}s is outside "
                                     f"that camera's recording (mic {-C.OFF[cam]:.1f}-{C.DUR[cam] - C.OFF[cam]:.1f}s); "
                                     "drop or move that range")
            # a shot can join pieces from different moments (jump cuts): frame each piece on its own face
            for p in pp:
                p["face"] = C.face_for(s["who"], [p["src"] + p["nf"] * FR * q for q in (0.2, 0.5, 0.8)])
                if p["nf"] * FR > 1.0:              # someone leaning mid-piece: pan from start face to end face
                    p["face_a"] = C.face_for(s["who"], [p["src"] + p["nf"] * FR * q for q in (0.05, 0.15)])
                    p["face_b"] = C.face_for(s["who"], [p["src"] + p["nf"] * FR * q for q in (0.85, 0.95)])
            res.append(dict(f0=s["f0"], f1=s["f1"], kind="F", who=s["who"], base=base, xin=xin, cam=cam,
                            face=pp[len(pp) // 2]["face"], parts=pp))
        else:
            prevwho = None
            D = (s["f1"] - s["f0"] + xin) * FR
            o = src_at(s["f0"]) + OO - xin * FR; still = False
            if pool:
                a_, b_ = pool[pi_]
                if pt + D > b_ - 0.1:                              # next clean view (cycle)
                    pi_ = (pi_ + 1) % len(pool); a_, b_ = pool[pi_]; pt = a_ + 0.3
                if pt + D > b_ - 0.1: pt = max(a_, b_ - D - 0.1)   # short view: use its tail
                o = pt; pt += D
            elif not C.fits(o, D) or not (CL[0] <= o and o + D <= CL[1]):
                cand = sorted([o + d / 10 for d in range(-1500, 1501)], key=lambda t: abs(t - o))
                ok = [t for t in cand if CL[0] <= t and t + D <= CL[1] and C.fits(t, D)]
                if ok: o = ok[0]
                else: still = True
            if not C.boxat(o): still = True              # no live post here: hold the nearest one in the clamp
            if res and any(r["kind"] == "T" for r in res):
                lastT = [r for r in res if r["kind"] == "T"][-1]
                if lastT["box"] != C.boxat(o): z = 1.0
            z0 = z; z1 = round(z0 + PUSH * D, 4)
            if z1 > ZMAX: z0 = 1.0; z1 = round(1.0 + PUSH * D, 4)
            z = z1
            bx = C.boxat(o) or next((r["box"] for r in res[::-1] if r["kind"] == "T"), None) or C.LIVE[0][2]
            if still and not C.boxat(o):            # hold the nearest good frame of the post inside the clamp
                cands = [(a, b, box) for a, b, box in C.LIVE if CL[0] <= a and b <= CL[1]]
                if cands:
                    a, b, box = min(cands, key=lambda q: abs(q[0] - o)); o = max(a, b - 0.2); bx = list(box)
            x0, y0, x1, y1 = bx
            if (x1 - x0) / (y1 - y0) > 1.15:
                cx = (x0 + x1) / 2; w = (y1 - y0) * 0.95; bx = [int(cx - w / 2), y0, int(cx + w / 2), y1]
            res.append(dict(f0=s["f0"], f1=s["f1"], kind="T", xin=xin, obs=round(o, 3), still=still,
                            box=bx, z0=round(z0, 4), z1=z1))
    return dict(id=S["id"], slug=S["slug"], kind=S["kind"], handle=S.get("handle"), title=S["title"],
                pieces=[dict(src0=p["src0"], nf=p["nf"], f0=p["f0"]) for p in P], shots=res, frames=NF,
                dur=round(NF * FR, 2), words=RW)


# ------------------------------------------------------------------ captions (port of ass80.py)
HDR = """[Script Info]
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
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(C, Pl, S, path):
    FIX = C.R.get("fix", {}) or {}; red = {str(r).upper() for r in S.get("red", [])}; dur = Pl["frames"] * FR

    def clean(w):
        w = FIX.get(w, FIX.get(w.rstrip(".,?!"), w))
        return re.sub(r"[^A-Za-z0-9'@_%$\- ]", "", w).upper().strip()
    words = [dict(w, txt=clean(w["w"])) for w in Pl["words"]]; words = [w for w in words if w["txt"]]
    cards, cur = [], []
    for k, w in enumerate(words):
        cur.append(w); nxt = words[k + 1] if k + 1 < len(words) else None
        txt = " ".join(x["txt"] for x in cur)
        if (nxt is None or len(cur) >= 3 or re.search(r"[.,?!]$", w["w"]) or nxt["piece"] != w["piece"]
                or nxt["rt"] - w["re"] > 0.3 or len(txt + " " + nxt["txt"]) > 15):
            cards.append(cur); cur = []
    evs = []
    for k, c in enumerate(cards):
        a = c[0]["rt"]; nx = cards[k + 1][0]["rt"] if k + 1 < len(cards) else dur
        b = nx if nx - c[-1]["re"] < 0.35 else c[-1]["re"] + 0.15
        b = min(max(b, a + 0.12), dur)
        txt = " ".join(" ".join(("{\\c&H2A1FD2&}" + p + "{\\c&HFFFFFF&}") if p.strip("'") in red else p
                                for p in x["txt"].split(" ")) for x in c)
        L = len(" ".join(x["txt"] for x in c)); fs = "" if L <= 12 else f"\\fs{int(112 * 12 / L)}"
        evs.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\pos(540,1170){fs}}}{txt}")
    tags = []
    if Pl["handle"]:
        L = len(Pl["handle"]) + 1; fs = "" if L <= 14 else f"\\fs{int(100 * 14 / L)}"
        for s in Pl["shots"]:
            if s["kind"] == "T":
                tags.append(f"Dialogue: 1,{ts(s['f0'] * FR + 0.03)},{ts(s['f1'] * FR)},Tag,,0,0,0,,"
                            f"{{\\pos(540,330)\\fad(150,150){fs}}}@{Pl['handle'].upper()}")
    Path(path).write_text(HDR + "\n".join(tags + evs) + "\n")
    return len(evs)


# ------------------------------------------------------------------ render (port of render80.py)
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30000/1001", "-an"]


def sh(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise SystemExit(f"FAIL {what}: {r.stderr[-1500:]}")


def face_shot(C, s, fn):
    base = s["base"]
    h = 1080 / base; w = h * 9 / 16
    total = sum(p["nf"] for p in s["parts"]); done = 0; parts = []
    def win(f):
        x0 = min(max(0, f[0] - w / 2), 1920 - w); y0 = min(max(0, f[1] - 0.30 * h), 1080 - h)
        return x0, y0
    for k, p in enumerate(s["parts"]):
        fx, fy = p.get("face", s["face"])
        x0, y0 = win((fx, fy))
        ax = 0.5; ay = min(0.45, (fy - y0) / h)
        za = 1 + 0.05 * done / total; zb = 1 + 0.05 * (done + p["nf"]) / total; D = p["nf"] * FR
        Z = f"({za:.5f}+({zb - za:.5f})*t/{D:.4f})"
        cx, cy = f"{int(x0)}", f"{int(y0)}"
        if "face_a" in p:
            (xa, ya), (xb, yb) = win(p["face_a"]), win(p["face_b"])
            if abs(xb - xa) > 60 or abs(yb - ya) > 40:     # smooth eased pan that follows the lean
                e = f"(0.5-0.5*cos(PI*min(1,t/{D:.4f})))"
                cx = f"'{xa:.1f}+({xb - xa:.1f})*{e}'"; cy = f"'{ya:.1f}+({yb - ya:.1f})*{e}'"
        vf = (f"setpts=PTS-STARTPTS,scale=1920:1080,crop={ev(w)}:{ev(h)}:{cx}:{cy},{C.GRADE[s['cam']]},"
              f"scale=w='ceil(1080*{Z}/2)*2':h='ceil(1920*{Z}/2)*2':eval=frame:flags=bicubic,"
              f"crop=1080:1920:x='(iw-1080)*{ax:.4f}':y='(ih-1920)*{ay:.4f}',format=yuv420p")
        pf = f"{fn}.p{k}.mp4"
        sh([media.FFMPEG, "-v", "error", "-y", "-ss", f"{p['src'] + C.OFF[s['cam']]:.3f}", "-i", C.SRC[s["cam"]],
            "-vf", vf, "-frames:v", str(p["nf"])] + ENC + [pf], "face part")
        parts.append(pf); done += p["nf"]
    if len(parts) == 1: os.replace(parts[0], fn); return
    lst = fn + ".txt"
    Path(lst).write_text("".join(f"file '{pf}'\n" for pf in parts))
    sh([media.FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", fn], "face concat")
    for pf in parts: os.remove(pf)
    os.remove(lst)


def tat_shot(C, s, fn):
    x0, y0, x1, y1 = s["box"]; bw, bh = x1 - x0, y1 - y0
    sc = min(960 / bw, 1180 / bh); fw, fh = ev(bw * sc), ev(bh * sc)      # whole post with air around it (R81)
    nf = s["f1"] - s["f0"] + s["xin"]; D = nf * FR
    Z = f"({s['z0']}+({s['z1']}-{s['z0']})*t/{D:.4f})"
    pre = "setpts=PTS-STARTPTS,fps=30000/1001"
    if s["still"]: pre += ",trim=end_frame=1,loop=loop=-1:size=1,setpts=N/(30000/1001)/TB"
    fc = (f"[0:v]{pre},crop={bw}:{bh}:{x0}:{y0},split[a][b];"
          f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.28:saturation=0.9[bg];"
          f"[b]scale=w='ceil({fw}*{Z}/2)*2':h='ceil({fh}*{Z}/2)*2':eval=frame:flags=bicubic,crop={fw}:{fh}[fg];"
          f"[bg][fg]overlay=(W-w)/2:880-h/2,format=yuv420p[v]")
    sh([media.FFMPEG, "-v", "error", "-y", "-ss", f"{s['obs']:.3f}", "-i", C.SRC["OBS"],
        "-filter_complex", fc, "-map", "[v]", "-frames:v", str(nf)] + ENC + [fn], "tattoo shot")


def mic_mix(C):
    wav = C.tmp / "mix48k.wav"
    if not wav.exists():
        ins = sum((["-i", m["file"]] for m in C.ep["mics"]), [])
        n = len(C.ep["mics"])
        fc = "".join(f"[{i}:a]pan=mono|c0=c0[m{i}];" for i in range(n)) + "".join(f"[m{i}]" for i in range(n)) + \
             f"amix=inputs={n}:normalize=0,aresample=48000[a]"
        sh([media.FFMPEG, "-v", "error", "-y"] + ins + ["-filter_complex", fc, "-map", "[a]", "-c:a", "pcm_s24le", str(wav)], "mic mix")
    return wav


def assemble(C, Pl, files, ass_path, fonts, out_mp4):
    S = Pl["shots"]; inputs, fl = [], []
    for k, fn in enumerate(files):
        inputs += ["-i", fn]; fl.append(f"[{k}:v]settb=AVTB,fps=30000/1001,format=yuv420p[s{k}]")
    cur = "s0"; dur = (S[0]["f1"] - S[0]["f0"]) * FR
    for k in range(1, len(S)):
        d = (S[k]["f1"] - S[k]["f0"]) * FR
        if S[k]["xin"]:
            x = S[k]["xin"] * FR
            fl.append(f"[{cur}][s{k}]xfade=transition=fade:duration={x:.4f}:offset={dur - x:.4f},settb=AVTB,fps=30000/1001[c{k}]")
        else:
            fl.append(f"[{cur}][s{k}]concat=n=2:v=1:a=0,settb=AVTB,fps=30000/1001[c{k}]")
        cur = f"c{k}"; dur += d
    ap = []
    for i, p in enumerate(Pl["pieces"]):
        d = p["nf"] * FR
        fl.append(f"[{len(files)}:a]atrim=start={p['src0']:.4f}:duration={d:.4f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.006,afade=t=out:st={d - 0.006:.4f}:d=0.006[a{i}]")
        ap.append(f"[a{i}]")
    fl.append(f"{''.join(ap)}concat=n={len(ap)}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,"
              "aformat=sample_fmts=fltp:channel_layouts=stereo[a]")
    fl.append(f"[{cur}]ass={ass_path}:fontsdir={fonts}[v]")
    pre = C.tmp / f"{Pl['id']}_pre.mp4"; graph = C.tmp / f"{Pl['id']}_graph.txt"
    graph.write_text(";\n".join(fl))
    sh([media.FFMPEG, "-v", "error", "-y"] + inputs + ["-i", str(mic_mix(C)), "-/filter_complex", str(graph),
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-map_metadata", "-1", "-map_chapters", "-1",
        "-shortest", str(pre)], "assemble")
    # -14.0 LUFS (+-0.2) and true peak <= -1.4 dBTP measured on the ENCODED file: AAC overshoots the limiter,
    # and the limiter shaves loudness, so measure the output and correct (up to 8 passes; usually 2-4).
    I0, _ = loudness(pre); gain = -14 - I0
    for lim in (0.80, 0.75, 0.70):                   # limiter fixed per round; only gain chases loudness
        for _ in range(5):
            sh([media.FFMPEG, "-v", "error", "-y", "-i", str(pre), "-c:v", "copy", "-af",
                f"volume={gain:.2f}dB,alimiter=limit={lim:.3f}:level=false:attack=2:release=40", "-c:a", "aac",
                "-b:a", "192k", "-movflags", "+faststart", str(out_mp4)], "loudness")
            I, TP = loudness(out_mp4)
            if abs(I + 14) <= 0.15: break
            gain += -14 - I
        if TP <= -1.45: break
    pre.unlink()


def loudness(path):
    r = subprocess.run([media.FFMPEG, "-nostdin", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    I = float([l for l in r.splitlines() if l.strip().startswith("I:")][-1].split()[1])
    TP = float([l for l in r.splitlines() if l.strip().startswith("Peak:")][-1].split()[1])
    return I, TP


# ------------------------------------------------------------------ verify (port of verify80.py)
_REC = None


def recognizer():
    global _REC
    if _REC is None:
        from .transcribe import MODEL
        import sherpa_onnx
        _REC = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(MODEL / "encoder.int8.onnx"), decoder=str(MODEL / "decoder.int8.onnx"),
            joiner=str(MODEL / "joiner.int8.onnx"), tokens=str(MODEL / "tokens.txt"),
            model_type="nemo_transducer", num_threads=8)
    return _REC


def verify(C, mp4, ass_path, sheet):
    rec = recognizer()
    a = subprocess.run([media.FFMPEG, "-v", "error", "-i", str(mp4), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(a, np.float32); s = rec.create_stream(); s.accept_waveform(16000, x); rec.decode_stream(s)
    words, cur = [], None
    for tk, tt in zip(s.result.tokens, s.result.timestamps):
        if tk.startswith(" ") or cur is None:
            if cur: words.append(cur)
            cur = [tk.strip(), tt]
        else: cur[0] += tk
    if cur: words.append(cur)
    evs = []
    for l in open(ass_path):
        if l.startswith("Dialogue: 0"):
            p = l.split(","); h, m, sx = p[1].split(":"); st = int(h) * 3600 + int(m) * 60 + float(sx)
            txt = re.sub(r"\{[^}]*\}", "", l.split(",,0,0,0,,")[-1]).strip()
            if txt: evs.append((st, txt.split()[0]))
    d = []
    for st, w0 in evs:
        c = [t for w, t in words if norm(w) == norm(w0) and abs(t - st) < 1.0]
        if c: d.append(min(c, key=lambda t: abs(t - st)) - st)
    d = np.abs(np.array(d)) if d else np.array([9.9])
    v = subprocess.run([media.FFMPEG, "-v", "error", "-i", str(mp4), "-vf", "scale=108:192,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    Y = np.frombuffer(v, np.uint8).reshape(-1, 192, 108).mean((1, 2))
    dips = [i for i in range(1, len(Y) - 1) if Y[i] < 0.8 * Y[i - 1] and Y[i] < 0.8 * Y[i + 1]]
    r = subprocess.run([media.FFMPEG, "-nostdin", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = float([l for l in r.splitlines() if l.strip().startswith("I:")][-1].split()[1])
    TP = float([l for l in r.splitlines() if l.strip().startswith("Peak:")][-1].split()[1])
    n = int(len(x) / 16000); ims = []
    for t in range(n):
        raw = subprocess.run([media.FFMPEG, "-v", "error", "-ss", str(t + 0.5), "-i", str(mp4), "-frames:v", "1", "-vf", "scale=180:320",
                              "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        if len(raw) == 180 * 320 * 3:
            im = np.frombuffer(raw, np.uint8).reshape(320, 180, 3).copy()
            cv2.putText(im, str(t), (4, 20), 0, 0.6, (0, 255, 255), 2); ims.append(im)
    while len(ims) % 12: ims.append(np.zeros((320, 180, 3), np.uint8))
    cv2.imwrite(str(sheet), np.vstack([np.hstack(ims[i:i + 12]) for i in range(0, len(ims), 12)]), [cv2.IMWRITE_JPEG_QUALITY, 75])
    ok = np.median(d) <= 0.05 and np.percentile(d, 90) <= 0.12 and not dips and abs(I + 14) <= 0.2 and TP <= -1.4
    return dict(dur=round(len(x) / 16000, 1), cards=len(evs), matched=len(d), median=round(float(np.median(d)), 3),
                p90=round(float(np.percentile(d, 90)), 3), dips=dips, lufs=I, tp=TP, ok=bool(ok), asr=s.result.text[:140])


# ------------------------------------------------------------------ run
def run(reels_yaml, ids=None, deliver=False, only_verify=False):
    C = Ctx(reels_yaml)
    fonts = C.tmp / "fonts"; fonts.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "legacy" / "BlackTakora-Regular.ttf", fonts / "BlackTakora-Regular.ttf")
    reels = [S for S in C.R["reels"] if not ids or S["id"] in ids]
    results = {}
    for S in reels:
        t0 = time.time()
        name = f"R{C.rel}_{S['id']}_{S['slug']}"
        mp4 = C.out / f"{name}.mp4"; ass_path = C.tmp / f"{name}.ass"; pj = C.tmp / f"{name}_plan.json"
        if not only_verify:
            Pl = plan(C, S); pj.write_text(json.dumps(Pl))
            ncards = write_ass(C, Pl, S, ass_path)
            files = []
            for k, s in enumerate(Pl["shots"]):
                fn = str(C.tmp / f"{S['id']}_{k:03d}.mp4"); files.append(fn)
                (face_shot if s["kind"] == "F" else tat_shot)(C, s, fn)
            assemble(C, Pl, files, ass_path, fonts, mp4)
            for fn in files: os.remove(fn)
            nT = sum(1 for r in Pl["shots"] if r["kind"] == "T"); nS = sum(1 for r in Pl["shots"] if r.get("still"))
            print(f"{name}: {Pl['dur']:.1f}s  shots {len(Pl['shots'])} (tattoo {nT}, stills {nS})  cards {ncards}  "
                  f"{time.time() - t0:.0f}s", flush=True)
        v = verify(C, mp4, ass_path, C.out / f"_sheet_{S['id']}.jpg")
        results[S["id"]] = v
        print(f"   verify: captions median {v['median']}s p90 {v['p90']}s ({v['matched']}/{v['cards']})  dips {v['dips']}  "
              f"{v['lufs']} LUFS  TP {v['tp']}  {'OK' if v['ok'] else 'CHECK'}", flush=True)
    write_docs(C, results)
    if deliver:
        dst = C.rec / C.out.name
        if dst.exists(): raise SystemExit(f"{dst} exists on the drive (never overwrite)")
        shutil.copytree(C.out, dst, ignore=shutil.ignore_patterns("_*"))
        bad = [p.name for p in C.out.iterdir() if not p.name.startswith("_") and not filecmp.cmp(p, dst / p.name, shallow=False)]
        if bad: raise SystemExit(f"copy verify failed: {bad}")
        print(f"Delivered {dst}")
    return results


def write_docs(C, results):
    reels = C.R["reels"]; rel = C.rel
    tattoo = [S for S in reels if S["kind"] == "tattoo"]; talk = [S for S in reels if S["kind"] == "talk"]
    order = []
    while tattoo or talk:                       # lead with a tattoo, slot the funny ones in between
        if tattoo: order.append(tattoo.pop(0))
        if tattoo: order.append(tattoo.pop(0))
        if talk: order.append(talk.pop(0))
    lines = [f"SHOP TALK R{rel} - REELS ({len(reels)})",
             "Suggested post order: " + ", ".join(S["id"] for S in order) + "   ·   collab-post each tattoo reel with the artist", ""]
    for S in order:
        mp4 = C.out / f"R{rel}_{S['id']}_{S['slug']}.mp4"
        dur = results.get(S["id"], {}).get("dur") or ""
        collab = f"  - collab @{S['handle']}" if S.get("handle") else ""
        tags = " ".join("#" + t.replace(" ", "").replace("_", "") for t in S["tags"])
        lines += [f"{mp4.name}  ({dur}s){collab}", f"Title: {S['title']}", f"Caption: {S['caption']}", tags, ""]
    (C.out / f"R{rel}_CAPTIONS.txt").write_text("\n".join(lines))
    day = dt.date.fromisoformat(str(C.R["start_date"]))
    with open(C.out / f"R{rel}_SHORTS_SCHEDULE.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["file", "title", "description", "tags", "publish_local"])
        for k, S in enumerate(order):
            w.writerow([f"R{rel}_{S['id']}_{S['slug']}.mp4", S["title"],
                        S["caption"] + "\\n\\nFull episode on the NLJBS channel.", "|".join(S["tags"]),
                        f"{day + dt.timedelta(days=k)} 18:00"])
