"""`nljbs switcher <edit.yaml>`: full auto edit -> ShopTalk_<date>_R<NN>_SWITCHER.xml.

Generalized from the R79/R80 builders (legacy/10.26.26/_claude_work/r80/scripts/build80.py, plan80.py).
Inputs: the edit config (episodes/R<NN>_edit.yaml), the work dir from probe/sync/transcribe/screen,
and the last finished edit as template (intro package, motion-effect template, outro shout-out graphics).

Main timeline: cold open -> 400-frame intro -> body (content cuts applied) with 10 angle nests on V1-V10
(only the chosen one enabled), V11 empty (multicam stack is off by default), V12 handle cards + shout-outs,
V13 image-insert placeholders. A1-A3 mics (mono), A4-A7 intro music from the template.
"""
import base64
import copy
import json
import math
import os
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import media

FPS = 30000 / 1001
INTRO = 400
TK = 8475667200          # pproTicks per frame at 29.97 (254016000000 / FPS)
W_, H_ = 1920, 1080

ANG_NAMES = ["1 AC + JAKE", "2 PORTER", "3 WIDE", "4 SPLIT - AC + JAKE + TATTOO", "5 SPLIT - PORTER + TATTOO",
             "6 SPLIT - WIDE + TATTOO", "7 PORTER PUNCH", "8 TATTOO ONLY", "9 AC TIGHT", "10 JAKE TIGHT"]
# angle indices (0-based)
A_TWO, A_POR, A_WIDE, A_SPL_TWO, A_SPL_POR, A_SPL_WIDE, A_POR_PUNCH, A_TAT, A_AC_T, A_JAKE_T = range(10)


# ---------------------------------------------------------------- geometry (from build80)
def place(src, out, scale):
    sx0, sy0, sx1, sy1 = src; ox0, oy0 = out; s = scale / 100
    PX = ox0 - (sx0 - 960) * s; PY = oy0 - (sy0 - 540) * s
    return dict(scale=scale, cx=(PX - 960) / 1920, cy=(PY - 540) / 1080,
                l=sx0 / 19.2, r=(1920 - sx1) / 19.2, t=sy0 / 10.8, b=(1080 - sy1) / 10.8)


def full(sc=100, cx=0.0, cy=0.0):
    return dict(scale=sc, cx=cx, cy=cy, l=0, r=0, t=0, b=0)


def tight(x0, y0, s):
    w, h = 1920 / s, 1080 / s
    x0 = min(max(0, x0), 1920 - w); y0 = min(max(0, y0), 1080 - h)
    return place((x0, y0, x0 + w, y0 + h), (0, 0), s * 100)


def plate(r, pad=0):
    x0, y0, x1, y1 = r
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad); x1 = min(1920, x1 + pad); y1 = min(1080, y1 + pad)
    return dict(scale=100, cx=0, cy=0, l=x0 / 19.2, r=(1920 - x1) / 19.2, t=y0 / 10.8, b=(1080 - y1) / 10.8)


def camfit(subj, bx0, by0, bw, bh):
    cx, mw = subj
    sw = min(1920, max(mw, 1080 * bw / bh)); sh = min(1080, sw * bh / bw)
    sx0 = min(max(0, cx - sw / 2), 1920 - sw); sy0 = (1080 - sh) * 0.35; sc = bw / sw * 100; dh = sh * sc / 100
    out = (bx0, by0 + (bh - dh) / 2)
    return place((sx0, sy0, sx0 + sw, sy0 + sh), out, sc), (out[0], out[1], out[0] + bw, out[1] + dh)


def panel(centered, PA):
    PH = 870; PW = PH * PA
    if centered:
        return (960 - PW / 2, 180, 960 + PW / 2, 1050)
    return (1880 - PW, 180, 1880, 1050)


def fitc(box, PA, pr):
    x0, y0, x1, y1 = box; w = x1 - x0; h = y1 - y0
    if w / h > PA:
        c = (x0 + x1) / 2; w = h * PA; x0 = c - w / 2; x1 = c + w / 2
    else:
        c = (y0 + y1) / 2; h = w / PA; y0 = c - h / 2; y1 = c + h / 2
    PW = pr[2] - pr[0]; PH = pr[3] - pr[1]; s = min(PW / (x1 - x0), PH / (y1 - y0))
    ox = pr[0] + (PW - (x1 - x0) * s) / 2; oy = pr[1] + (PH - (y1 - y0) * s) / 2
    return place((x0, y0, x1, y1), (ox, oy), s * 100)


# ---------------------------------------------------------------- speaker runs (from plan80, N mics)
def speaker_runs(L10, names, B0, B1, min_run=2.0, lead_db=4.0):
    n = L10.shape[1] // 5
    P = 10 ** (L10[:, :n * 5] / 10)
    L = 10 * np.log10(P.reshape(len(names), n, 5).mean(2) + 1e-12)          # 50 ms
    act = L.max(0) > np.percentile(L.max(0), 35)
    o = np.argsort(-L, axis=0); top = o[0]
    lead = np.take_along_axis(L, o[:1], 0)[0] - np.take_along_axis(L, o[1:2], 0)[0]
    lab = np.where(act & (lead > lead_db), top + 1, 0)
    N = n // 2; l10 = lab[:N * 2].reshape(N, 2)                              # 100 ms
    k0, k1 = int(B0 * 10), min(N, int(B1 * 10))
    cur, seq = 1, []
    for i in range(k0, k1):
        ww = l10[max(0, i - 6):i + 7].ravel(); ww = ww[ww > 0]
        s = cur if len(ww) == 0 else int(np.bincount(ww, minlength=len(names) + 1).argmax())
        cur = s; seq.append(s)
    runs = []
    for j, s in enumerate(seq):
        t = k0 / 10 + j * 0.1
        if runs and runs[-1][2] == s:
            runs[-1][1] = t + 0.1
        else:
            runs.append([t, t + 0.1, s])
    changed = True
    while changed:
        changed = False
        for i, r in enumerate(runs):
            if r[1] - r[0] < min_run and len(runs) > 1:
                if i == 0: runs[1][0] = r[0]
                elif i == len(runs) - 1: runs[i - 1][1] = r[1]
                elif runs[i - 1][1] - runs[i - 1][0] >= runs[i + 1][1] - runs[i + 1][0]: runs[i - 1][1] = r[1]
                else: runs[i + 1][0] = r[0]
                runs.pop(i); changed = True; break
        m = []
        for r in runs:
            if m and m[-1][2] == r[2]: m[-1][1] = r[1]
            else: m.append(r)
        runs = m
    runs[0][0] = B0; runs[-1][1] = B1
    return [(a, b, names[s - 1]) for a, b, s in runs], L


# ---------------------------------------------------------------- content cuts
def silence_cuts(words, Lmix, B0, B1, gap_max, gap_keep, protect):
    """Trim word gaps > gap_max down to gap_keep, only where the mics stay quiet (no laughs/crosstalk)."""
    floor = np.percentile(Lmix, 35)
    pad = gap_keep / 2
    cuts = []
    ws = [w for w in words if B0 <= w["t0"] <= B1]
    for w, nx in zip(ws[:-1], ws[1:]):
        a = w["t1"] + pad; b = nx["t0"] - pad
        if nx["t0"] - w["t1"] <= gap_max or b - a < 0.25:
            continue
        if any(pa < b and a < pb for pa, pb in protect):
            continue
        seg = Lmix[int(a * 100):int(b * 100)]
        if len(seg) and np.percentile(seg, 90) > floor + 8:
            continue
        cuts.append((round(a, 3), round(b, 3)))
    return cuts


# ---------------------------------------------------------------- plates
def font(size, bold=True):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def card_png(out, header_img=None, typed=None):
    """Handle card: IG post header at 1.7x (or typed @handle) on #1C2225, 6 px white border, top right."""
    card = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    if header_img is not None:
        hi = header_img.resize((int(header_img.width * 1.7), int(header_img.height * 1.7)), Image.LANCZOS)
    else:
        f = font(40); tw = int(f.getlength(typed))
        hi = Image.new("RGB", (tw + 70, 127), (0x1C, 0x22, 0x25))
        ImageDraw.Draw(hi).text((35, 63), typed, font=f, fill=(245, 245, 245), anchor="lm")
    bw = 6; w, h = hi.width + 2 * bw, hi.height + 2 * bw
    x0 = 1880 - w; y0 = 36 - bw + (127 - hi.height) // 2
    d = ImageDraw.Draw(card)
    d.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), fill=(255, 255, 255, 255))
    bg = Image.new("RGB", hi.size, (0x1C, 0x22, 0x25)); bg.paste(hi, (0, 0))
    card.paste(bg, (x0 + bw, y0 + bw))
    card.save(out)


def image_slot_png(out, label, side):
    """Placeholder for Avery's image: white-bordered box with the label. Replace in Premiere."""
    img = Image.new("RGBA", (W_, H_), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    bw, size = 8, 640
    x0 = 1880 - size if side == "right" else 40
    y0 = 200
    d.rectangle((x0, y0, x0 + size, y0 + size), fill=(255, 255, 255, 255))
    d.rectangle((x0 + bw, y0 + bw, x0 + size - bw, y0 + size - bw), fill=(40, 40, 44, 235))
    f1, f2 = font(54), font(30, bold=False)
    d.text((x0 + size / 2, y0 + 220), "IMAGE", font=f1, fill=(255, 210, 0, 255), anchor="mm")
    words, lines, cur = label.split(), [], ""
    for wd in words:
        if f2.getlength(cur + " " + wd) > size - 90:
            lines.append(cur); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    for i, ln in enumerate(lines):
        d.text((x0 + size / 2, y0 + 300 + i * 42), ln, font=f2, fill=(235, 235, 235, 255), anchor="mm")
    img.save(out)


# ---------------------------------------------------------------- main build
def run(edit_yaml, deliver=False, variant=None):
    E = yaml.safe_load(Path(edit_yaml).read_text())
    ep = yaml.safe_load(Path(os.path.expanduser(E["episode"])).read_text())
    work = Path(ep["work_dir"]); rec = Path(ep["recording_folder"])
    rel = E["release"]; mm, dd, yy = ep["recording_date"].split(".")
    name = f"ShopTalk_{mm}-{dd}-{yy}_R{rel}_SWITCHER" + (f"_{variant}" if variant else "")
    PL_NAME = f"R{rel}_PLATES"; plates = work / PL_NAME; (plates / "holds").mkdir(parents=True, exist_ok=True)

    # ---- sources and placed offsets (from the sync XML report)
    rep = yaml.safe_load((work / "sync_report.yaml").read_text())
    probe = yaml.safe_load((work / "probe.yaml").read_text())
    SRC, OFF, NATIVE, FILES = {}, {}, {}, {}
    for c in ep["cameras"]:
        k = {"ave": "AVE", "093a": "093A", "wide": "C"}[c["kind"]]
        SRC[k] = c["file"]
    SRC["OBS"] = ep["obs"][0]
    graded = (E.get("grade") or {}).get("use_graded")
    for k, p in SRC.items():
        fn = Path(p).name; s = probe["sources"][fn]; v = s["video"]
        OFF[k] = rep[fn]["xml_offset_s"]                  # offsets measured on the originals
        tb, ntsc = media.xml_rate(v["fps"])
        NATIVE[k] = (tb, "TRUE" if ntsc else "FALSE", int(round(s["duration"] * v["fps"])))
        FILES[k] = p
        if graded and Path(p).stem in E["grade"]["cameras"]:
            gp = Path(p).with_name(Path(p).stem + "_GRADED.mp4")   # same frames + rate as the original
            if not gp.exists():
                raise SystemExit(f"{gp.name} not on the drive yet: run `nljbs grade --deliver` first")
            FILES[k] = str(gp)
    mic_dur = min(m["duration"] for m in probe["mics"].values())
    MICS = []
    for i, m in enumerate(ep["mics"], 1):
        k = f"M{i}"; FILES[k] = m["file"]; OFF[k] = 0.0
        NATIVE[k] = (30, "TRUE", int(mic_dur * FPS)); MICS.append((k, f"MIC {i} {m['who'].upper()}"))
    names = [m["who"].upper() for m in ep["mics"]]

    B0, B1 = E["body"]; OUT0 = E["outro"]
    B0f = int(round(B0 * FPS)); NB = int(round(B1 * FPS)) - B0f
    Of = {k: int(round(o * FPS)) for k, o in OFF.items()}
    G = lambda m: int(round(m * FPS)) - B0f

    # ---- data
    words = json.loads((work / "words.json").read_text())
    L10 = np.load(work / "levels.npy")
    Lmix = 10 * np.log10(np.sum(10 ** (L10 / 10), axis=0) + 1e-12)
    runs_scr = json.loads((work / "screen.json").read_text())
    diff = np.load(work / "obs_diff10.npy")
    oo = OFF["OBS"]

    # ---- speaker runs
    runs, _ = speaker_runs(L10, names, B0, B1)

    # ---- screen pieces per section (mic time)
    hold_k = set(E.get("hold_runs", []))
    SECT = []
    holds = []
    for S in E["sections"]:
        sa, sb = S["a"], S["b"]
        live = []          # (a, b, box) in mic time
        prev_end = None; prev_box = None
        for r in runs_scr:
            a, b = r["a"] + oo, r["b"] + oo
            if b <= sa or a >= sb:
                prev_end, prev_box = b, (r["box"] if r["k"] not in hold_k and r["box"] else prev_box); continue
            # moving gap before this run: a video post if it moves steadily for >= 3 s
            if prev_end is not None and prev_box and a - prev_end >= 3.0:
                g = diff[int((prev_end - oo) * 10):int((a - oo) * 10)]
                if len(g) and np.median(g) < 4.0:
                    live.append([max(sa, prev_end), min(sb, a), prev_box])
            if r["k"] not in hold_k and r["box"]:
                live.append([max(sa, a), min(sb, b), r["box"]])
                prev_box = r["box"]
            prev_end = b
        live = [p for p in live if p[1] - p[0] >= 0.4]
        pieces, t = [], sa
        for a, b, box in live:
            if a > t + 0.05:
                pieces.append(dict(m0=t, m1=a, kind="hold"))
            pieces.append(dict(m0=max(a, t), m1=b, kind="live", box=box)); t = b
        if t < sb - 0.05:
            pieces.append(dict(m0=t, m1=sb, kind="hold"))
        for i, p in enumerate(pieces):
            if p["kind"] != "hold":
                continue
            prv = next((pieces[j] for j in range(i - 1, -1, -1) if pieces[j]["kind"] == "live"), None)
            nxt = next((pieces[j] for j in range(i + 1, len(pieces)) if pieces[j]["kind"] == "live"), None)
            src = prv or nxt
            p["box"] = src["box"]
            st = (src["m1"] - 0.15) if prv else (src["m0"] + 0.2)
            p["still"] = f"hold_{S['id']}_{st - oo:07.2f}.png"; p["still_obs_t"] = st - oo
            holds.append((p["still_obs_t"], p["still"]))
        asp = [(p["box"][2] - p["box"][0]) / (p["box"][3] - p["box"][1]) for p in pieces if p["kind"] == "live"]
        PA = float(np.clip(np.median(asp) if asp else 0.8, 0.6, 0.95))
        SECT.append(dict(**S, pieces=pieces, PA=PA))
        print(f"{S['id']} @{S['handle']}  {sa:.1f}-{sb:.1f}  pieces {len(pieces)}  PA {PA:.2f}  "
              f"live {sum(p['m1'] - p['m0'] for p in pieces if p['kind'] == 'live'):.0f}s  "
              f"hold {sum(p['m1'] - p['m0'] for p in pieces if p['kind'] == 'hold'):.0f}s")

    # protect video playback from silence cuts
    protect = []
    for S in SECT:
        for i, p in enumerate(S["pieces"]):
            pass
    for r0, r1 in zip(runs_scr[:-1], runs_scr[1:]):
        a, b = r0["b"] + oo, r1["a"] + oo
        g = diff[int(r0["b"] * 10):int(r1["a"] * 10)]
        if b - a >= 3.0 and len(g) and np.median(g) < 4.0:
            protect.append((a, b))

    # ---- content cuts
    cuts = silence_cuts(words, Lmix, B0, B1, E["gap_max"], E["gap_keep"], protect)
    cuts += [tuple(c) for c in E.get("cuts", [])]
    removed = np.zeros(NB, bool)
    for a, b in cuts:
        removed[max(0, G(a)):max(0, G(b))] = True
    print(f"content cuts: {len(cuts)}  removed {removed.sum() / FPS:.1f}s of {NB / FPS:.1f}s "
          f"({100 * removed.mean():.1f}%)")

    # ---- shot plan (mic time)
    def section_at(t):
        return next((S for S in SECT if S["a"] <= t < S["b"]), None)

    other = {"093A": "AVE", "AVE": "093A"}
    cam_of = {n: E["cast"][n]["cam"] for n in names}
    full_ang = {"093A": A_POR, "AVE": A_TWO, "C": A_WIDE}
    split_ang = {"093A": A_SPL_POR, "AVE": A_SPL_TWO, "C": A_SPL_WIDE}
    punch_ang = {"PORTER": A_POR_PUNCH, "AC": A_AC_T, "JAKE": A_JAKE_T}

    shots, nshort = [], Counter()
    alt_cycle = ["wide", "react", "punch"]; ai = 0
    for a, b, spk in runs:
        d = b - a
        if d <= 6.5:
            nshort[spk] += 1
            kind = "punch" if (nshort[spk] % 3 == 0 and 3.0 < d < 8.0) else "main"
            shots.append([a, b, spk, kind])
        else:
            # uneven rhythm so long runs don't cut on a metronome: speaker shots long, cutaways short
            PAT = [5.2, 2.8, 4.3, 3.1, 4.8, 2.6, 3.9, 3.4]
            t0, j = a, 0
            while t0 < b - 0.01:
                L_ = PAT[(ai + j) % len(PAT)]
                t1 = b if b - (t0 + L_) < 2.2 else t0 + L_
                k = "main" if j % 2 == 0 else alt_cycle[ai % 3]
                if j % 2: ai += 1
                shots.append([t0, t1, spk, k]); t0 = t1; j += 1

    def angle_for(t, spk, kind):
        cam = cam_of[spk]
        if t >= OUT0:
            return {"main": full_ang[cam], "punch": full_ang[cam], "wide": A_WIDE, "react": full_ang[other[cam]]}[kind]
        if section_at(t):
            return {"main": split_ang[cam], "wide": A_SPL_WIDE, "react": split_ang[other[cam]],
                    "punch": full_ang[cam]}[kind]
        return {"main": full_ang[cam], "punch": punch_ang[spk], "wide": A_WIDE, "react": full_ang[other[cam]]}[kind]

    # overrides: tattoo-only beats, image slots (force the speaker's full camera so the image has room)
    over = [(a, b, A_TAT) for a, b in E.get("tattoo_only", [])]
    for a, dur, side, label in E.get("images", []):
        spk = next((s for x, y, s in runs if x <= a < y), names[0])
        cam = cam_of[spk]
        ang = full_ang[cam]
        if cam == "AVE":                       # two faces on AVE: go tight on the side the card leaves clear
            ang = A_AC_T if side == "right" else A_JAKE_T
        over.append((a, a + dur, ang))
    bounds = sorted({B0, B1} | {x for s in shots for x in s[:2]} | {x for o in over for x in o[:2]}
                    | {S["a"] for S in SECT} | {S["b"] for S in SECT} | {OUT0})
    bounds = [x for x in bounds if B0 <= x <= B1]
    segs = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b - a < 1e-6:
            continue
        mid = (a + b) / 2
        ov = next((o for o in over if o[0] <= mid < o[1]), None)
        if ov:
            ang = ov[2]
        else:
            sh = next(s for s in shots if s[0] <= mid < s[1] + 1e-9)
            kind = sh[3]
            if section_at(mid) and kind == "punch" and sh[1] - sh[0] > 4.5:
                kind = "main"
            ang = angle_for(mid, sh[2], kind)
        if segs and segs[-1]["ang"] == ang:
            segs[-1]["b"] = b
        else:
            segs.append(dict(a=a, b=b, ang=ang))

    # merge shots that end up < 1.6 s on the cut timeline
    def cut_len(a, b):
        ga, gb = max(0, G(a)), min(NB, G(b))
        return (gb - ga - removed[ga:gb].sum()) / FPS

    out = []
    for s in segs:
        if out and (cut_len(s["a"], s["b"]) < 1.6 and s["ang"] != A_TAT or out[-1]["ang"] == s["ang"]):
            out[-1]["b"] = s["b"]
        else:
            out.append(s)
    segs = out
    ang_g = np.zeros(NB, int); seg_g = np.zeros(NB, int)
    for i, s in enumerate(segs):
        ga, gb = max(0, G(s["a"])), min(NB, G(s["b"]))
        ang_g[ga:gb] = s["ang"]; seg_g[ga:gb] = i

    # ---- trailer
    def snap(t):
        i = int(round(t * 100)); w = Lmix[i - 6:i + 7]
        return (i - 6 + int(np.argmin(w))) / 100 if len(w) else t

    TR, t = [], 0
    for a, b, ang, card in E["trailer"]:
        a2, b2 = snap(a), snap(b); ga, gb = G(a2), G(b2)
        TR.append(dict(a=a2, b=b2, ga=ga, gb=gb, ang=ang - 1, card=card, start=t, end=t + gb - ga)); t += gb - ga
    TRL = t

    # ---- plates
    print("Rendering plates…", flush=True)
    ffm = media.FFMPEG
    def grab(src, tsec, outp, vf=None):
        if not Path(outp).exists():
            cmd = [ffm, "-v", "error", "-y", "-ss", f"{tsec:.3f}", "-i", str(src), "-frames:v", "1"]
            if vf: cmd += ["-vf", vf]
            subprocess.run(cmd + [str(outp)], check=True)
    wide_png = plates / "_wide.png"
    grab(SRC["C"], 300, wide_png, "scale=1920:1080,eq=contrast=1.15:gamma=1.2:saturation=1.25")
    Image.open(wide_png).convert("RGB").filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.55)).save(plates / f"R{rel}_backdrop.png")
    Image.new("RGB", (W_, H_), (255, 255, 255)).save(plates / f"R{rel}_white.png")
    Image.new("RGB", (W_, H_), (0, 0, 0)).save(plates / f"R{rel}_black.png")
    for S in SECT:
        c = S["card"]; outp = plates / f"card_{S['handle']}.png"
        if c.get("typed"):
            card_png(outp, typed="@" + S["handle"])
        else:
            im = Image.open(work / "screen" / f"{c['run']:03d}.jpg").convert("RGB")
            card_png(outp, header_img=im.crop(tuple(c["avatar"])))
    for t_obs, fn in holds:
        grab(SRC["OBS"], t_obs, plates / "holds" / fn)
    for i, (a, dur, side, label) in enumerate(E.get("images", [])):
        image_slot_png(plates / f"image_{i + 1:02d}.png", label, side)

    BASE_PL = rec / PL_NAME
    def still(k): return k.startswith(("BG", "WH", "BK", "CARD_", "H_", "IMG_"))
    FILES.update({"BG": BASE_PL / f"R{rel}_backdrop.png", "WH": BASE_PL / f"R{rel}_white.png",
                  "BK": BASE_PL / f"R{rel}_black.png"})
    for S in SECT: FILES["CARD_" + S["handle"]] = BASE_PL / f"card_{S['handle']}.png"
    for _, fn in holds: FILES["H_" + fn] = BASE_PL / "holds" / fn
    for i in range(len(E.get("images", []))): FILES[f"IMG_{i + 1:02d}"] = BASE_PL / f"image_{i + 1:02d}.png"
    for k in FILES:
        if still(k): NATIVE[k] = (30, "TRUE", 107892)

    # ---- template
    TPL = ET.parse(E["template"]).getroot(); seqT = TPL.find("sequence")
    bm_tpl = next((f for c in TPL.iter("clipitem") for f in c.findall("filter")
                   if f.findtext("effect/effectid") == "basic" and f.find(".//parameter[parameterid='leftcrop']") is not None), None)
    if bm_tpl is None:
        raise SystemExit("template has no Basic Motion filter with crop parameters")

    def safe(k): return "".join(ch if ch.isalnum() else "_" for ch in k)
    def rate(tb=30, nt="TRUE"):
        r = ET.Element("rate"); ET.SubElement(r, "timebase").text = str(tb); ET.SubElement(r, "ntsc").text = nt; return r
    used = set()
    def fileel(k):
        fe = ET.Element("file", id=f"r{rel}-file-" + safe(k))
        if k in used: return fe
        used.add(k); tb, nt, dur = NATIVE[k]
        ET.SubElement(fe, "name").text = Path(FILES[k]).name
        ET.SubElement(fe, "pathurl").text = "file://localhost" + quote(str(FILES[k]))
        fe.append(rate(tb, nt)); ET.SubElement(fe, "duration").text = str(dur)
        m = ET.SubElement(fe, "media")
        if not k.startswith("M"):
            v = ET.SubElement(m, "video"); sc = ET.SubElement(v, "samplecharacteristics")
            ET.SubElement(sc, "width").text = "1920"; ET.SubElement(sc, "height").text = "1080"
        if k in ("AVE", "093A", "C", "OBS") or k.startswith("M"):
            a = ET.SubElement(m, "audio"); sc = ET.SubElement(a, "samplecharacteristics")
            mic = k.startswith("M")
            ET.SubElement(sc, "depth").text = "16"; ET.SubElement(sc, "samplerate").text = "44100" if mic else "48000"
            ET.SubElement(a, "channelcount").text = "2"
        return fe
    def bm(g):
        f = copy.deepcopy(bm_tpl)
        for p in f.iter("parameter"):
            pid = p.findtext("parameterid"); v = p.find("value")
            for kf in p.findall("keyframe"): p.remove(kf)
            if v is None: continue
            if pid == "scale": v.text = f"{g['scale']:.4f}"
            elif pid == "rotation": v.text = "0"
            elif pid == "center": v.find("horiz").text = f"{g['cx']:.6f}"; v.find("vert").text = f"{g['cy']:.6f}"
            elif pid == "centerOffset": v.find("horiz").text = "0"; v.find("vert").text = "0"
            elif pid in ("leftcrop", "rightcrop", "topcrop", "bottomcrop"): v.text = f"{g[pid[0]]:.4f}"
        return f
    cid = [0]
    def clip(k, start, end, geo, name=None, enabled=True, inp=None):
        cid[0] += 1; L_ = end - start
        i0 = 0 if still(k) else (B0f - Of[k] + start if inp is None else inp)
        c = ET.Element("clipitem", id=f"r{rel}c-{cid[0]}")
        ET.SubElement(c, "masterclipid").text = f"r{rel}-mc-" + safe(k)
        # HARD RULE: camera/OBS clipitem name = source file name
        ET.SubElement(c, "name").text = Path(FILES[k]).name if k in SRC else (name or Path(FILES[k]).name)
        ET.SubElement(c, "enabled").text = "TRUE" if enabled else "FALSE"
        ET.SubElement(c, "duration").text = str(NATIVE[k][2] if still(k) else L_); c.append(rate())
        for t_, v in (("start", start), ("end", end), ("in", i0), ("out", i0 + L_)):
            ET.SubElement(c, t_).text = str(v)
        c.append(fileel(k))
        if geo is not None: c.append(bm(geo))
        return c
    def seq_shell(sid, nm, dur):
        s = ET.Element("sequence", id=sid); ET.SubElement(s, "name").text = nm
        ET.SubElement(s, "duration").text = str(dur); s.append(rate())
        tc = ET.SubElement(s, "timecode"); tc.append(rate()); ET.SubElement(tc, "string").text = "00:00:00;00"
        ET.SubElement(tc, "frame").text = "0"; ET.SubElement(tc, "displayformat").text = "NDF"
        med = ET.SubElement(s, "media"); vid = ET.SubElement(med, "video")
        fmt = ET.SubElement(ET.SubElement(vid, "format"), "samplecharacteristics"); fmt.append(rate())
        for t_, v in (("width", "1920"), ("height", "1080"), ("pixelaspectratio", "square"), ("fielddominance", "none")):
            ET.SubElement(fmt, t_).text = v
        return s, med, vid
    def close(tr, enabled=True):
        ET.SubElement(tr, "enabled").text = "TRUE" if enabled else "FALSE"; ET.SubElement(tr, "locked").text = "FALSE"

    # ---- angle nests
    T = E["tights"]
    SUBJ = {k: tuple(v) for k, v in E["subject"].items()}
    FULLSC = {"AVE": full(), "093A": full(), "C": full()}
    ANG = [("full", "AVE", full()), ("full", "093A", full()), ("full", "C", full()),
           ("A", "AVE", None), ("A", "093A", None), ("A", "C", None),
           ("full", "093A", tight(*T["PORTER"])), ("T", "C", None),
           ("full", "AVE", tight(*T["AC"])), ("full", "AVE", tight(*T["JAKE"]))]
    PIECES = []
    for S in SECT:
        for p in S["pieces"]:
            g0, g1 = max(0, G(p["m0"])), min(NB, G(p["m1"]))
            if g1 > g0: PIECES.append([g0, g1, p, S])
    BW = 6
    def build_angle(i):
        kind, cam, geo = ANG[i]
        s, med, vid = seq_shell(f"r{rel}-ang-{i}", f"R{rel} ANG {ANG_NAMES[i]}", NB)
        if kind == "full":
            tr = ET.SubElement(vid, "track"); tr.append(clip(cam, 0, NB, geo)); close(tr); return s
        trk = {t_: ET.SubElement(vid, "track") for t_ in range(1, 7)}
        t_ = 0
        for g0, g1, p, S in PIECES + [(NB, NB, None, None)]:
            if g0 > t_: trk[1].append(clip(cam, t_, g0, FULLSC[cam]))
            if p is None: break
            PA = S["PA"]; pr = panel(kind == "T", PA)
            trk[1].append(clip("BG", g0, g1, full(), name="BACKDROP"))
            trk[2].append(clip("WH", g0, g1, plate(pr, BW), name="BORDER post"))
            trk[3].append(clip("BK", g0, g1, plate(pr), name="MATTE"))
            if kind == "A":
                gc, cr = camfit(SUBJ[cam], 40, 180, pr[0] - 70, 870)
                trk[4].append(clip("WH", g0, g1, plate(cr, BW), name="BORDER cam"))
                trk[5].append(clip(cam, g0, g1, gc))
            geo2 = fitc(p["box"], PA, pr)
            if p["kind"] == "live": trk[6].append(clip("OBS", g0, g1, geo2))
            else: trk[6].append(clip("H_" + p["still"], g0, g1, geo2, name="HOLD " + p["still"]))
            t_ = g1
        for tr in trk.values(): close(tr)
        return s
    def nest(start, end, inp, enabled, nm, mcid):
        cid[0] += 1; L_ = end - start
        c = ET.Element("clipitem", id=f"r{rel}n-{cid[0]}")
        ET.SubElement(c, "masterclipid").text = mcid; ET.SubElement(c, "name").text = nm
        ET.SubElement(c, "enabled").text = "TRUE" if enabled else "FALSE"
        ET.SubElement(c, "duration").text = str(NB); c.append(rate())
        for t_, v in (("start", start), ("end", end), ("in", inp), ("out", inp + L_)): ET.SubElement(c, t_).text = str(v)
        return c
    defined = set()
    def nest_angle(i, start, end, inp, enabled):
        c = nest(start, end, inp, enabled, "ANG " + ANG_NAMES[i], f"r{rel}-mc-ang-{i}")
        if i in defined: ET.SubElement(c, "sequence", id=f"r{rel}-ang-{i}")
        else: defined.add(i); c.append(build_angle(i))
        return c

    # ---- main timeline
    BODY0 = TRL + INTRO
    FINAL, KEPT, t, g = [], [], BODY0, 0
    while g < NB:
        if removed[g]: g += 1; continue
        h = g
        while h < NB and not removed[h] and ang_g[h] == ang_g[g] and seg_g[h] == seg_g[g]: h += 1
        FINAL.append(dict(start=t, end=t + (h - g), inp=g, ang=int(ang_g[g])))
        if KEPT and KEPT[-1][1] == g: KEPT[-1] = (KEPT[-1][0], h, KEPT[-1][2])
        else: KEPT.append((g, h, t))
        t += h - g; g = h
    NF = t
    def g2main(gg):
        for a, b, ts in KEPT:
            if a <= gg < b: return ts + gg - a
            if gg < a: return ts
        return NF

    main, med, vid = seq_shell(f"r{rel}-main", name, NF)
    Ffiles = {f.get("id"): f for f in TPL.iter("file") if len(f)}
    seenF = set()
    i0_, i1_ = E["template_intro"]; dt = TRL - i0_
    def tpl_items(kind, idx):
        trs = seqT.findall(f"media/{kind}/track"); out = []
        if idx >= len(trs): return out
        for c in trs[idx]:
            if c.tag not in ("clipitem", "transitionitem", "generatoritem"): continue
            nm = c.findtext("name") or ""
            if nm.startswith("ANG ") or nm.startswith("@") or nm.startswith("MIC "): continue
            s_, e_ = int(c.findtext("start")), int(c.findtext("end"))
            inwin = (i0_ <= s_ < i1_ or (s_ == -1 and i0_ < e_ <= i1_)) and (e_ <= i1_ or e_ == -1)
            if not inwin: continue
            cc = copy.deepcopy(c)
            if cc.get("id"): cc.set("id", f"r{rel}intro-" + cc.get("id"))
            for l in cc.findall("link"): cc.remove(l)
            # Intro b-roll keeps Avery's own Lumetri from the template (single-use clips, not episode cameras).
            # Episode cameras never get clip-level color: LUTs go on their source master clips in Premiere.
            fe = cc.find("file")
            if fe is not None:
                fid = fe.get("id")
                if fid in seenF:
                    for ch in list(fe): fe.remove(ch)
                else:
                    seenF.add(fid)
                    if len(fe) == 0 and fid in Ffiles:
                        j = list(cc).index(fe); cc.remove(fe); cc.insert(j, copy.deepcopy(Ffiles[fid]))
            for tag in ("start", "end"):
                e = cc.find(tag)
                if e is not None and int(e.text) >= 0: e.text = str(int(e.text) + dt)
            # HARD RULE also for intro b-roll: camera clipitem name = file name
            fe2 = cc.find("file")
            fdef = fe2 if fe2 is not None and len(fe2) else (Ffiles.get(fe2.get("id")) if fe2 is not None else None)
            fnm = fdef.findtext("name") if fdef is not None else None
            if fnm and fnm.upper().endswith(".MP4") and cc.findtext("name") != fnm:
                cc.find("name").text = fnm
            out.append(cc)
        return out
    def sort_track(tr):
        items = sorted([c for c in tr if c.tag in ("clipitem", "transitionitem", "generatoritem")],
                       key=lambda c: (int(c.findtext("start")) if int(c.findtext("start")) >= 0 else int(c.findtext("end")) - 1))
        for c in items: tr.remove(c)
        for c in items: tr.append(c)

    for ti in range(10):
        tr = ET.SubElement(vid, "track")
        for Tt in TR: tr.append(nest_angle(ti, Tt["start"], Tt["end"], Tt["ga"], Tt["ang"] == ti))
        for cc in tpl_items("video", ti): tr.append(cc)
        for s_ in FINAL: tr.append(nest_angle(ti, s_["start"], s_["end"], s_["inp"], s_["ang"] == ti))
        sort_track(tr); close(tr)
    close(ET.SubElement(vid, "track"))                    # V11: multicam stack off by default

    # V12: handle cards + shout-outs
    tr = ET.SubElement(vid, "track")
    PA_OF = {S["handle"]: S["PA"] for S in SECT}
    def dx_of(h): PW = 870 * PA_OF[h]; return 960 - (1880 - PW / 2)
    def card_item(h, a, b, dx):
        k = "CARD_" + h; c = clip(k, a, b, full(cx=dx / 1920) if dx else None, name="@" + h)
        c.find("out").text = str(b - a); return c
    for Tt in TR:
        if Tt["card"]:
            tr.append(card_item(Tt["card"], Tt["start"], Tt["end"], dx_of(Tt["card"]) if Tt["ang"] == A_TAT else 0))
    cards = []
    for S in SECT:
        a = g2main(max(0, G(S["a"]))); b = g2main(min(NB, G(S["b"])))
        cps = [a] + sorted({x for f_ in FINAL if f_["ang"] == A_TAT and f_["end"] > a and f_["start"] < b
                            for x in (max(a, f_["start"]), min(b, f_["end"]))}) + [b]
        for p0, p1 in zip(cps[:-1], cps[1:]):
            if p1 <= p0: continue
            isT = any(f_["ang"] == A_TAT and f_["start"] <= p0 and f_["end"] >= p1 for f_ in FINAL)
            tr.append(card_item(S["handle"], p0, p1, dx_of(S["handle"]) if isT else 0))
        cards.append((S["handle"], a, b))
    gfx = {}
    for c in seqT.iter("clipitem"):
        if c.findtext("name") == "Graphic":
            for e in c.findall("filter/effect"):
                gfx.setdefault((e.findtext("name") or "").strip(), c)
    for key, (a, b) in E.get("shoutouts", {}).items():
        src = gfx.get(key)
        if src is None:
            print(f"  ! shout-out graphic {key!r} not in template"); continue
        s_ = g2main(G(a)); e_ = g2main(G(b))
        cc = copy.deepcopy(src); cc.set("id", f"r{rel}gfx-" + safe(key))
        for l in cc.findall("link"): cc.remove(l)
        i0 = int(cc.findtext("in"))
        cc.find("start").text = str(s_); cc.find("end").text = str(e_); cc.find("out").text = str(i0 + e_ - s_)
        if cc.find("pproTicksIn") is not None:
            cc.find("pproTicksIn").text = str(i0 * TK); cc.find("pproTicksOut").text = str((i0 + e_ - s_) * TK)
        fe = cc.find("file")
        if fe is not None:
            fid = fe.get("id")
            if fid in seenF: [fe.remove(ch) for ch in list(fe)]
            else:
                seenF.add(fid)
                if len(fe) == 0 and fid in Ffiles:
                    j = list(cc).index(fe); cc.remove(fe); cc.insert(j, copy.deepcopy(Ffiles[fid]))
        tr.append(cc)
    sort_track(tr); close(tr)

    # V13: image-insert placeholders
    tr = ET.SubElement(vid, "track"); imgs = []
    for i, (a, dur, side, label) in enumerate(E.get("images", [])):
        s_ = g2main(G(a)); e_ = g2main(G(a + dur))
        if e_ - s_ < 15: continue
        c = clip(f"IMG_{i + 1:02d}", s_, e_, None, name=f"IMAGE {i + 1:02d}: {label}"); c.find("out").text = str(e_ - s_)
        tr.append(c); imgs.append((i + 1, s_, e_, label))
    close(tr)

    # ---- audio
    aud = ET.SubElement(med, "audio"); ET.SubElement(aud, "numOutputChannels").text = "2"
    af = ET.SubElement(ET.SubElement(aud, "format"), "samplecharacteristics")
    ET.SubElement(af, "depth").text = "16"; ET.SubElement(af, "samplerate").text = "48000"
    NA = len(seqT.findall("media/audio/track"))
    segs_audio = [(Tt["ga"], Tt["gb"], Tt["start"]) for Tt in TR] + KEPT
    for ti in range(max(NA, len(MICS))):
        tr = ET.SubElement(aud, "track")
        if ti < len(MICS):
            k, nm = MICS[ti]
            tr.set("premiereTrackType", "Mono")
            for n_, (a, b, ts) in enumerate(segs_audio):
                L_ = b - a; i0 = B0f + a
                c = ET.SubElement(tr, "clipitem", id=f"r{rel}-mic{ti + 1}-{n_}", premiereChannelType="mono")
                ET.SubElement(c, "masterclipid").text = f"r{rel}-mc-" + k; ET.SubElement(c, "name").text = nm
                ET.SubElement(c, "enabled").text = "TRUE"; ET.SubElement(c, "duration").text = str(NATIVE[k][2]); c.append(rate())
                for t_, v in (("start", ts), ("end", ts + L_), ("in", i0), ("out", i0 + L_)): ET.SubElement(c, t_).text = str(v)
                c.append(fileel(k))
                st_ = ET.SubElement(c, "sourcetrack"); ET.SubElement(st_, "mediatype").text = "audio"
                ET.SubElement(st_, "trackindex").text = "1"
        else:
            for cc in tpl_items("audio", ti): tr.append(cc)
        sort_track(tr); close(tr)

    # ---- episode number in the intro graphic
    old = E["template_ep"]; new = f"ep:{rel}"
    assert len(old) == len(new), "ep text length changed: patch the uint32 length prefix"
    for f in main.iter("filter"):
        nm = f.findtext("effect/name") or ""
        if nm.strip() == old:
            f.find("effect/name").text = nm.replace(old, new)
            for p in f.iter("parameter"):
                if p.findtext("name") == "Source Text":
                    raw = base64.b64decode(p.findtext("value"))
                    p.find("value").text = base64.b64encode(raw.replace(old.encode(), new.encode())).decode()

    xm = ET.Element("xmeml", version="4"); xm.append(main); ET.indent(xm, space=" ")
    outp = work / f"{name}.xml"
    with open(outp, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'); f.write(ET.tostring(xm, encoding="unicode"))
    ET.parse(outp)

    # ---- report
    def tc(fr): s = fr / FPS; return f"{int(s // 60)}:{s % 60:05.2f}"
    tot = Counter()
    for s_ in FINAL: tot[ANG_NAMES[s_["ang"]]] += (s_["end"] - s_["start"]) / FPS
    shotlens, cur = [], None
    for s_ in FINAL:
        if cur and cur[1] == s_["ang"] and cur[2] == s_["start"]: cur[0] += s_["end"] - s_["start"]; cur[2] = s_["end"]
        else:
            if cur: shotlens.append(cur[0] / FPS)
            cur = [s_["end"] - s_["start"], s_["ang"], s_["end"]]
    shotlens.append(cur[0] / FPS)
    body_s = sum(tot.values())
    lines = [f"{name}", f"runtime {tc(NF)}  (cold open {tc(TRL)}, intro ends {tc(BODY0)})",
             f"body raw {NB / FPS / 60:.1f} min -> {body_s / 60:.1f} min after {len(cuts)} cuts "
             f"({100 * (1 - body_s / (NB / FPS)):.1f}% removed)",
             f"shots {len(shotlens)}  median {np.median(shotlens):.1f}s  p25 {np.percentile(shotlens, 25):.1f}  p75 {np.percentile(shotlens, 75):.1f}",
             "angle balance:"]
    for k, v in sorted(tot.items(), key=lambda x: -x[1]):
        lines.append(f"   {k:32s} {v:6.1f}s {100 * v / body_s:5.1f}%")
    for h, a, b in cards: lines.append(f"card @{h:22s} {tc(a)} - {tc(b)}")
    for Tt in TR: lines.append(f"cold open {tc(Tt['start'])}-{tc(Tt['end'])}  {ANG_NAMES[Tt['ang']]:30s} mic {Tt['a']:.2f}-{Tt['b']:.2f}")
    for n_, s_, e_, label in imgs: lines.append(f"IMAGE {n_:02d}  {tc(s_)}-{tc(e_)}  {label}")
    report = "\n".join(lines)
    (work / f"{name}_report.txt").write_text(report + "\n")
    (work / f"{name}_plan.json").write_text(json.dumps(dict(FINAL=FINAL, KEPT=KEPT, NF=NF, TR=TR, cuts=cuts, runs=runs), default=float))
    print(report)
    print(f"\nXML: {outp}  ({outp.stat().st_size // 1024} KB)\nPlates: {plates}")

    if deliver:
        deliver_files(outp, plates, rec)
    return outp


def deliver_files(xml_path, plates, rec):
    """Copy XML + plates folder to the recording folder. New names only; verify every file."""
    import filecmp, shutil
    dst_pl = rec / plates.name; dst_x = rec / xml_path.name
    if dst_x.exists():
        raise SystemExit(f"Not delivering: {dst_x.name} already exists on the drive (never overwrite).")
    src_files = [p for p in plates.rglob("*") if p.is_file() and not p.name.startswith("_")]
    clash = [p for p in src_files if (dst_pl / p.relative_to(plates)).exists()
             and not filecmp.cmp(p, dst_pl / p.relative_to(plates), shallow=False)]
    if clash:
        raise SystemExit(f"Not delivering: plates differ from the ones on the drive: {[p.name for p in clash][:5]}")
    for p in src_files:                                    # copy only what's missing; identical files are reused
        d = dst_pl / p.relative_to(plates)
        if not d.exists():
            d.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, d)
    shutil.copy2(xml_path, dst_x)
    bad = [p for p in src_files if not filecmp.cmp(p, dst_pl / p.relative_to(plates), shallow=False)]
    if bad or not filecmp.cmp(xml_path, dst_x, shallow=False):
        raise SystemExit(f"Copy verify FAILED: {bad}")
    print(f"Delivered: {dst_x}\n           {dst_pl}/ ({sum(1 for _ in dst_pl.rglob('*.png'))} png)")
