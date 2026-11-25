"""`palefire cut <shoot.yaml> [ids...] [--preview]`: build vertical reels from a cut plan on the music grid.

Per reel in the YAML:
  1. Resolve each dialogue segment to whole words: every word overlapping [a, b] is kept, with breathing room
     (HEAD_PAD before the first word, TAIL_PAD after the last) unless a neighbouring word is closer.
  2. Lay out segments back to back; snap each cut to the nearest music beat (Beat This grid) by giving or
     taking silence at the outgoing shot's tail or head. Never below MIN_HEAD / MIN_TAIL, never into a word.
     With `payoff` + `break_at`, the music is placed so that segment starts on the track's break.
  3. Write <id>.xml (xmeml v4, 1080x1920, 29.97): V1 camera, V2 score counter stills, V3 title line, V4 caption cards (Montserrat PNGs),
     A1/A2 camera audio (none under `react` shots, which hide Avery's off-camera calls),
     A3/A4 music with Audio Levels keyframes. Basic Motion and Audio Levels filters are copied from Avery's
     own Premiere export (template_xml) so the structure is Premiere's.
  4. Write <id>.srt: 1-3 word caption cards, with `fix:` spellings applied (beer names, Pale Fire).
  5. --preview: render <id>_preview.mp4 with the LUT + finish, punch-ins, counter, music mix, -14 LUFS.
Everything is written to <work>/cuts/. Nothing is written to the drive.

Avery's rule (2026-11-19): no rushed cuts. Whole sentences with breathing room beat a fast shot median.
"""
import copy
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

from nljbs import media
from nljbs.transcribe import SR as ASR_SR, band_levels

FPS = 30000 / 1001
PUNCH = 115.0
VW, VH = 1080, 1920
HEAD_PAD, TAIL_PAD = 0.20, 0.35   # breathing room around speech
MIN_HEAD, MIN_TAIL = 0.12, 0.25   # beat-snapping may not trim below these
GAP = 0.03                        # keep this far from a neighbouring word
STILL_DUR = 107892                # Premiere's still-image duration (as in STIENHOLDING / switcher)
FONT = "/System/Library/Fonts/Helvetica.ttc"
OVERLAY_Y = 1030                  # top of the counter / title box: chest height, under the face on 115% punch-ins, captions sit below
CAPTION_FONT = Path("~/Library/Fonts/Montserrat-VariableFont_wght.ttf").expanduser()
CAPTION_WEIGHT, CAPTION_SIZE, CAPTION_Y = "ExtraBold", 84, 1300   # Y = caption line centre, under the counter
SILENT = ("action", "react")      # kinds with no dialogue: times used as given; react also mutes camera audio


def fr(t):
    return int(round(t * FPS))


def seg_scale(s):
    """Basic Motion scale (%) for a segment: punch-ins at PUNCH, everything else full frame."""
    return s.get("scale", PUNCH if s["kind"] == "punch" else 100.0)


def db_to_lin(db):
    return 10 ** (db / 20)


def pathurl(p):
    return "file://localhost" + quote(str(p))


# ---------- plan ----------

def load_words(work, stem):
    return json.loads((work / "transcripts" / f"{stem}.words.json").read_text())


MIN_SHOT = 12        # frames (0.4 s): no picture, main or b-roll, may be shorter; anything less reads as a flash
VOICE_DROP = 14.0    # dB under the word's peak that counts as the voice having stopped
SHARP_MIN = 40.0     # median Laplacian variance at 270x480: under this a chosen shot is soft or out of focus
BLUR_DIP = 0.5       # a frame under half the sharpness its shot reaches (75th percentile nearby) is motion blur
BLUR_ABS = 130.0     # ...and under this absolute sharpness (every blurred frame Avery flagged measured 11-121)


def voice_end(lv, t0, t1, limit):
    """Where a word really stops. The ASR gives each word a start but only an estimated end, and a shouted
    "Singooo!" runs well past it. Walk the 150-3500 Hz level forward until it falls VOICE_DROP under the word's
    peak, capped at the next word (limit) and 1.5 s past the estimate. lv: band levels in dB per 10 ms hop."""
    i0, i1 = int(t0 * 100), max(int(t0 * 100) + 1, int(t1 * 100))
    if i0 >= len(lv):
        return t1
    ref = float(np.max(lv[i0:min(i1 + 5, len(lv))]))
    i, stop = i1, min(len(lv), int(min(limit, t1 + 1.5) * 100))
    while i < stop and lv[i] > ref - VOICE_DROP:
        i += 1
    return max(t1, min(i * 0.01 + 0.05, limit))


def resolve(s, ws, dur, lv=None):
    """Expand a dialogue segment to whole words plus breathing room. Action segments keep their times."""
    if s["kind"] in SILENT:
        s["first"] = s["last"] = None
        return s
    a, b = s["inp"], s["out"]
    idx = [i for i, w in enumerate(ws) if w["t0"] < b + 0.05 and w["t1"] > a - 0.05]
    if not idx:
        raise SystemExit(f"{s['clip']} {a}-{b}: no words in range")
    i0, i1 = idx[0], idx[-1]
    s["first"], s["last"] = ws[i0], ws[i1]
    # GAP from neighbouring words, but never past our own first/last word when speakers run words together
    prev_end = min(ws[i0 - 1]["t1"] + GAP, ws[i0]["t0"]) if i0 > 0 else 0.0
    next_start = max(ws[i1 + 1]["t0"] - GAP, ws[i1]["t1"]) if i1 + 1 < len(ws) else dur
    if "end" in s:  # hard out point, for a next word the ASR timed late (heard onset, not transcript)
        next_start = min(next_start, float(s["end"]))
    if "start" in s:  # hard in point, e.g. past blurred frames where the camera was still moving
        prev_end = max(prev_end, float(s["start"]))
    if lv is not None:  # the last word ends where the voice stops, not where the ASR guessed
        heard = voice_end(lv, ws[i1]["t0"], ws[i1]["t1"], next_start)
        s["last"] = dict(ws[i1], t1=round(heard, 3), t1_asr=ws[i1]["t1"])
        next_start = max(next_start, heard)
    s["inp"] = max(ws[i0]["t0"] - HEAD_PAD, prev_end, 0.0)
    s["out"] = min(s["last"]["t1"] + TAIL_PAD, next_start, dur)
    s["prev_end"], s["next_start"] = prev_end, next_start
    return s


JOIN = 0.40   # pieces of one take closer than this play as one continuous shot


def join_takes(segs):
    """Back-to-back pieces of one take (a line running into the pour, a wide then a punch-in) meet exactly,
    so the cut is a scale change with no skipped or repeated frames. Snapping leaves these joins alone."""
    for s, n in zip(segs, segs[1:]):
        if s["clip"] == n["clip"] and s["inp"] < n["inp"] < s["out"] + JOIN:  # gap or overlap in one take
            mid = n["inp"]                                   # keep the incoming piece's start
            if s["first"] is not None:                       # never into the outgoing line's last word
                mid = max(mid, s["last"]["t1"] + MIN_TAIL)
            if n["first"] is not None:                       # nor into the incoming line's first word
                mid = min(mid, n["first"]["t0"] - MIN_HEAD)
            s["out"] = n["inp"] = mid
            s["join_next"] = n["join_prev"] = True
    return segs


def slack(s):
    """How far this shot's length can shrink / grow: (tail_trim, tail_ext, head_trim, head_ext), all >= 0."""
    if s.get("join_prev"):  # head is tied to the previous piece of the same take
        tt, te, _, _ = _slack(s)
        return tt, te, 0.0, 0.0
    return _slack(s)


def _slack(s):
    if s["first"] is None:  # action shot: keep at least 1.0 s; trim only, since pours are cut from one take
        room = max(0.0, (s["out"] - s["inp"]) - 1.0)  # in back-to-back pieces and growing one would repeat frames
        return room / 2, 0.0, room / 2, 0.0
    tail_trim = max(0.0, s["out"] - (s["last"]["t1"] + MIN_TAIL))
    head_trim = max(0.0, (s["first"]["t0"] - MIN_HEAD) - s["inp"])
    tail_ext = max(0.0, s["next_start"] - s["out"])
    head_ext = max(0.0, s["inp"] - s["prev_end"])
    return tail_trim, tail_ext, head_trim, head_ext


def snap_plan(segs, beats, music_at, window):
    """Move each cut onto the nearest beat by changing the outgoing shot's length (silence only)."""
    t = 0.0
    for s in segs[:-1]:
        if s.get("join_next"):  # continuous take: no snapping at this cut
            t += s["out"] - s["inp"]
            continue
        target = t + (s["out"] - s["inp"]) + music_at
        tt, te, ht, he = slack(s)
        for b in sorted(beats, key=lambda b: abs(b - target))[:3]:
            delta = b - target
            if abs(delta) > window:
                continue
            if delta < 0 and -delta <= tt + ht:
                use = min(-delta, tt)
                s["out"] -= use
                s["inp"] += -delta - use
            elif delta >= 0 and delta <= te + he:
                use = min(delta, te)
                s["out"] += use
                s["inp"] -= delta - use
            else:
                continue
            s["snapped"] = round(delta, 3)
            break
        t += s["out"] - s["inp"]
    return segs


TURN = {0: "null", -90: "transpose=2", 90: "transpose=1", 180: "hflip,vflip"}


def broll_frames(segs):
    """Lay each segment's b-roll on exact frames and leave no slivers: a gap of main picture under MIN_SHOT
    between two cutaways, before the first or after the last is absorbed into the b-roll, and a cutaway under
    MIN_SHOT is dropped. Moving a cutaway's start earlier moves its source in point with it."""
    for s in segs:
        wins = sorted(([max(0, fr(b["at"])), min(fr(b["at"]) + fr(b["dur"]), s["len"]), b]
                       for b in s.get("broll_items", [])), key=lambda w: w[0])
        out = []
        for w in wins:
            if out and w[0] - out[-1][1] < MIN_SHOT:
                out[-1][1] = max(out[-1][1], w[0])  # close the sliver between cutaways
                w[0] = out[-1][1]
            if w[1] - w[0] >= MIN_SHOT:
                out.append(w)
        if out and out[0][0] < MIN_SHOT:
            out[0][0] = 0
        if out and s["len"] - out[-1][1] < MIN_SHOT:
            out[-1][1] = s["len"]
        s["broll_frames"] = [dict(b, a=a, e=e, src=max(0.0, b["src"] - (fr(b["at"]) - a) / FPS)) for a, e, b in out]


def picture(segs):
    """The picture as the viewer sees it: [(label, start frame, frames)], cutaways included."""
    shots = []
    for s in segs:
        t = 0
        for w in s.get("broll_frames", []):
            if w["a"] > t:
                shots.append((s["clip"], s["start"] + t, w["a"] - t))
            shots.append((f"{w['clip']} (b-roll)", s["start"] + w["a"], w["e"] - w["a"]))
            t = w["e"]
        if s["len"] > t:
            shots.append((s["clip"], s["start"] + t, s["len"] - t))
    return shots


def crop_x(cx):
    """ffmpeg crop x that puts source point cx (0-1 across the filled frame) in the middle, kept inside the picture."""
    return f"x='max(0,min(iw-ow,{cx:.4f}*iw-ow/2))'"


def face_cx(path, t0, t1, rot, n=5):
    """Where the faces sit across a wide shot (0-1), for the 9:16 crop: median centre of the biggest face in n frames
    spread over [t0, t1]. None when no face shows (the crop stays centred)."""
    import cv2
    xs = []
    for k in range(n):
        t = t0 + (t1 - t0) * (k + 0.5) / n
        raw = subprocess.run([media.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                              "-vf", f"{TURN[rot]},scale=640:-2,format=bgr24", "-f", "rawvideo", "-"],
                             capture_output=True, check=True).stdout
        h = len(raw) // (640 * 3)
        if not h:
            continue
        det = cv2.FaceDetectorYN.create(str(media.WORK_ROOT / "models" / "yunet.onnx"), "", (640, h), 0.6)
        found = det.detect(np.frombuffer(raw, np.uint8)[: h * 640 * 3].reshape(h, 640, 3).copy())[1]
        if found is not None:
            x, _, w, fh = max(found[:, :4].tolist(), key=lambda f: f[2] * f[3])
            xs.append((x + w / 2) / 640)
    return float(np.median(xs)) if xs else None


def sharpness(path, t, dur, rot, cx=0.5):
    """Per-frame sharpness (Laplacian variance on a 270x480 gray copy). Camera shake shows up as motion blur:
    calibrated on the Basye shoot, where Avery's "too shaky" shot measured 11 against 85-165 for clean shots."""
    w, h = 270, 480
    raw = subprocess.run([media.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-t", f"{dur:.3f}", "-i", path,
                          "-vf", f"{TURN[rot]},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}:{crop_x(cx)},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8)[: len(raw) // (w * h) * w * h].reshape(-1, h, w).astype(np.float32)
    return np.array([np.var(a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]) for a in f])


EDGE = 6            # frames at each end of a shot that must be sharp and (for dialogue) show the speaker
_FACES = None


def faces(path, t, n, rot, cx=0.5):
    """[bool] per frame for n frames from t: is a face in frame (YuNet, the model nljbs reels use)."""
    global _FACES
    import cv2
    if _FACES is None:
        _FACES = cv2.FaceDetectorYN.create(str(media.WORK_ROOT / "models" / "yunet.onnx"), "", (270, 480), 0.6)
    raw = subprocess.run([media.FFMPEG, "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path, "-frames:v", str(n),
                          "-vf", f"{TURN[rot]},scale=270:480:force_original_aspect_ratio=increase,crop=270:480:{crop_x(cx)},format=bgr24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8)[: len(raw) // (270 * 480 * 3) * 270 * 480 * 3].reshape(-1, 480, 270, 3)
    return [_FACES.detect(np.ascontiguousarray(x))[1] is not None for x in f]


def edge_checks(segs, cams):
    """Hanging frames at the ends of every visible stretch of a main shot: motion blur at either edge, and on
    dialogue shots the speaker out of frame at the start or end (walked off, camera swung away)."""
    fail = []
    for s in segs:
        path, rot = cams[s["clip"]][0], s.get("rot", 0)
        sh = sharpness(path, s["in_f"] / FPS, s["len"] / FPS, rot, s.get("cx", 0.5))
        if not len(sh):
            continue
        t, spans = 0, []
        for w in s.get("broll_frames", []):
            if w["a"] > t:
                spans.append((t, w["a"]))
            t = w["e"]
        if s["len"] > t:
            spans.append((t, s["len"]))
        for a, e in spans:
            if not len(sh[a:e]):
                continue
            # motion blur is a sudden dip: judge the edge frames against the half second beside them, so a shot
            # that softens slowly (subject moving off the focus plane) is not mistaken for a whip
            for name, lo, hi, ref in (("start", a, min(a + EDGE, e), sh[a:min(a + EDGE + 30, e)]),
                                      ("end", max(a, e - EDGE), e, sh[max(a, e - EDGE - 30):e])):
                r = float(np.percentile(ref, 75))  # the sharpness this stretch settles at, not dragged down by the blur
                dips = int(np.sum((sh[lo:hi] < BLUR_DIP * r) & (sh[lo:hi] < BLUR_ABS)))
                if dips >= 2:
                    fail.append(f"{(s['start'] + lo) / FPS:6.2f}s  {s['clip']} @ {(s['in_f'] + lo) / FPS:.2f}s: {dips} blurred "
                                f"frames at the {name} of the shot (edge {' '.join(f'{v:.0f}' for v in sh[lo:hi])}, "
                                f"around {r:.0f})")
            if s["first"] is not None and not s.get("vo"):  # dialogue: the speaker must be in frame (vo: off-camera narrator)
                for name, lo in (("start", a), ("end", max(a, e - EDGE))):
                    seen = faces(path, (s["in_f"] + lo) / FPS, EDGE, rot, s.get("cx", 0.5))
                    if seen and sum(seen) < len(seen) / 2:
                        fail.append(f"{(s['start'] + lo) / FPS:6.2f}s  {s['clip']}: speaker out of frame at the {name} "
                                    f"of the shot ({sum(seen)}/{len(seen)} frames with a face)")
    return fail


def checks(segs, cams):
    """Frame-level checks before anything is delivered. Returns (failures, warnings) as text lines."""
    fail, warn = [], []
    for label, start, n in picture(segs):
        if n < MIN_SHOT:
            fail.append(f"{start / FPS:6.2f}s  {label}: {n}-frame shot (minimum {MIN_SHOT})")
    fail += edge_checks(segs, cams)
    for s in segs:
        if s["first"] is not None and s["out"] < s["last"]["t1"] + 0.10:
            warn.append(f"{s['start'] / FPS:6.2f}s  {s['clip']}: cut lands {s['out'] - s['last']['t1']:+.2f}s from the "
                        f"end of \"{s['last']['w']}\"")
        # picture choices (action, react, b-roll) must be sharp: no soft shots, no motion-blurred frames
        windows = [(s["clip"], s["inp"], s["len"] / FPS, s.get("rot", 0), s["start"], s.get("cx", 0.5))] if s["first"] is None else []
        windows += [(w["clip"], w["src"], (w["e"] - w["a"]) / FPS, w["rot"], s["start"] + w["a"], w.get("cx", 0.5))
                    for w in s.get("broll_frames", [])]
        for clip, t, dur, rot, at, cx in windows:
            sh = sharpness(cams[clip][0], t, dur, rot, cx)
            if not len(sh):
                continue
            med = float(np.median(sh))
            dips = np.where((sh < BLUR_DIP * med) & (sh < BLUR_ABS))[0]
            if med < SHARP_MIN:
                fail.append(f"{at / FPS:6.2f}s  {clip} @ {t:.2f}s: soft shot (sharpness {med:.0f}, minimum {SHARP_MIN:.0f})")
            elif len(dips) >= 2:
                fail.append(f"{at / FPS:6.2f}s  {clip} @ {t:.2f}s: {len(dips)} motion-blurred frames, first at "
                            f"{(at + dips[0]) / FPS:.2f}s in the reel")
    return fail, warn


def layout(segs):
    """Frame positions from the running sum in seconds, so rounding never accumulates past half a frame."""
    t, start = 0.0, 0
    for i, s in enumerate(segs):
        t += s["out"] - s["inp"]
        end = fr(t)
        s["start"], s["len"] = start, end - start
        # source in-frame; a joined piece starts on the frame after its neighbour ends, so no frame repeats or drops
        s["in_f"] = segs[i - 1]["in_f"] + segs[i - 1]["len"] if s.get("join_prev") else fr(s["inp"])
        start = end
    return start


def reel_time(segs, seg_idx, src_t):
    s = segs[seg_idx]
    return s["start"] / FPS + (src_t - s["inp"])


# ---------- captions ----------

def apply_fixes(ws, fixes):
    """Phrase-level spelling fixes on word tokens. Keys match consecutive words, ignoring case/punctuation.

    The replacement takes the first matched word's slot (timing spans the whole match); trailing
    punctuation of the last matched word is kept.
    """
    norm = lambda w: re.sub(r"[^\w']", "", w).lower()
    keys = sorted(((k.lower().split(), v) for k, v in (fixes or {}).items()), key=lambda kv: -len(kv[0]))
    out, i = [], 0
    while i < len(ws):
        for kw, rep in keys:
            n = len(kw)
            if [norm(w["w"]) for w in ws[i:i + n]] == kw:
                tail = re.search(r"[^\w']*$", ws[i + n - 1]["w"]).group(0)
                out.append(dict(ws[i], w=rep + tail, t1=ws[i + n - 1]["t1"]))
                i += n
                break
        else:
            out.append(ws[i])
            i += 1
    return out


def captions(segs, words, fixes):
    cards = []
    for s in segs:
        if s["first"] is None:
            continue
        off = s["start"] / FPS - s["inp"]
        ws = apply_fixes([w for w in words[s["clip"]] if s["inp"] <= w["t0"] < s["out"] - 0.05], fixes)
        cur = []
        for i, w in enumerate(ws):
            cur.append(w)
            end_here = (len(cur) == 3 or re.search(r"[.?!,]$", w["w"]) or i == len(ws) - 1
                        or ws[i + 1]["t0"] - w["t1"] > 0.30)
            if end_here:
                a = max(cur[0]["t0"] + off, s["start"] / FPS)
                b = min(cur[-1]["t1"] + off + 0.15, (s["start"] + s["len"]) / FPS)
                cards.append((a, b, " ".join(x["w"] for x in cur).rstrip(".,")))
                cur = []
    for i in range(len(cards) - 1):  # close gaps under 2 frames so cards don't flicker
        a, b, txt = cards[i]
        if cards[i + 1][0] - b < 2 / FPS:
            cards[i] = (a, cards[i + 1][0], txt)
    return cards


def mont(size, weight=None):
    f = ImageFont.truetype(str(CAPTION_FONT), size)
    f.set_variation_by_name(weight or CAPTION_WEIGHT)
    return f


def caption_png(text, out):
    """Transparent 1080x1920 caption card: Montserrat ExtraBold, white with a black edge, centred at CAPTION_Y."""
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(CAPTION_FONT), CAPTION_SIZE)
    f.set_variation_by_name(CAPTION_WEIGHT)
    size = CAPTION_SIZE
    while d.textlength(text, font=f) > VW - 120 and size > 50:  # long words: shrink to fit the frame
        size -= 4
        f = ImageFont.truetype(str(CAPTION_FONT), size)
        f.set_variation_by_name(CAPTION_WEIGHT)
    d.text((VW / 2, CAPTION_Y), text, font=f, fill=WHITE, anchor="mm", stroke_width=7, stroke_fill=(0, 0, 0, 255))
    im.save(out)


def caption_states(reel, cards, out_dir):
    cap_dir = out_dir / f"{reel['id']}_captions"
    cap_dir.mkdir(exist_ok=True)
    for old in cap_dir.glob("*.png"):
        old.unlink()
    states = []
    for i, (a, b, txt) in enumerate(cards):
        png = cap_dir / f"cap_{i:03d}.png"
        caption_png(txt, png)
        fa, fb = fr(a), fr(b)
        if fb > fa:
            states.append((png, fa, fb))
    return states


def srt(cards):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(cards, 1))


# ---------- score counter ----------

GREEN, RED, WHITE = (52, 199, 89, 255), (235, 64, 52, 255), (255, 255, 255, 255)


def counter_png(results, total, out):
    """Transparent 1080x1920 overlay: 'n/3' and one dot per beer (green right, red wrong, ring pending)."""
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    right = sum(r == "right" for r in results)
    text = f"{right}/{total}"
    f = mont(76)  # Montserrat ExtraBold, same as the captions
    tw = d.textlength(text, font=f)
    dot, gap = 30, 16
    dots_w = total * dot + (total - 1) * gap
    w = int(max(tw, dots_w) + 80)
    x0, y0, h = (VW - w) // 2, OVERLAY_Y, 170
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=34, fill=(0, 0, 0, 150))
    d.text(((VW - tw) / 2, y0 + 14), text, font=f, fill=WHITE)
    dx = (VW - dots_w) // 2
    for i in range(total):
        cx, cy = dx + i * (dot + gap), y0 + 118
        box = [cx, cy, cx + dot, cy + dot]
        if i < len(results):
            d.ellipse(box, fill=GREEN if results[i] == "right" else RED)
        else:
            d.ellipse(box, outline=WHITE, width=3)
    im.save(out)


def title_png(text, out):
    """Transparent 1080x1920 overlay: one static title line in the same box style as the counter."""
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = mont(68)
    tw = d.textlength(text, font=f)
    w, h = int(tw + 80), 120
    x0 = (VW - w) // 2
    d.rounded_rectangle([x0, OVERLAY_Y, x0 + w, OVERLAY_Y + h], radius=30, fill=(0, 0, 0, 150))
    d.text((VW / 2, OVERLAY_Y + h / 2), text, font=f, fill=WHITE, anchor="mm")
    im.save(out)


def title_states(reel, segs, out_dir):
    """title_card: {text, until}: the line shows from frame 0 until segment `until` starts."""
    tc = reel.get("title_card")
    if not tc:
        return []
    png = out_dir / f"{reel['id']}_title.png"
    title_png(tc["text"], png)
    return [(png, 0, segs[tc["until"]]["start"])]


def counter_states(reel, segs, total, out_dir):
    """[(png path, start frame, end frame)] covering counter_from .. end of reel."""
    if "score" not in reel:
        return []
    n = reel.get("score_total", 3)
    events = sorted((fr(reel_time(segs, i, t)), r) for i, t, r in reel["score"])
    start = segs[reel["counter_from"]]["start"]
    states, results, t0 = [], [], start
    for ev_f, r in events + [(total, None)]:
        png = out_dir / f"{reel['id']}_score_{len(results)}{''.join(x[0] for x in results)}.png"
        counter_png(results, n, png)
        if ev_f > t0:
            states.append((png, t0, ev_f))
        if r:
            results.append(r)
        t0 = max(t0, ev_f)
    return states


# ---------- xml ----------

def template_filters(template_xml):
    r = ET.parse(template_xml).getroot()
    bm = al = None
    for f in r.iter("filter"):
        n = f.findtext("effect/name")
        if n == "Basic Motion" and bm is None:
            bm = f
        if n == "Audio Levels" and al is None:
            al = f
    if bm is None or al is None:
        raise SystemExit(f"{template_xml}: needs a Basic Motion and an Audio Levels filter to copy")
    return bm, al


def bm_filter(tpl, scale, rotation=0, horiz=0.0, keys=None):
    """keys: [(source frame, scale %)] for a slow zoom; horiz: centre offset as a fraction of the sequence width."""
    f = copy.deepcopy(tpl)
    for p in f.iter("parameter"):
        pid, v = p.findtext("parameterid"), p.find("value")
        for kf in p.findall("keyframe"):
            p.remove(kf)
        if v is None:
            continue
        if pid == "scale":
            v.text = f"{scale:.4f}"
            for when, sc in keys or []:
                k = ET.SubElement(p, "keyframe")
                ET.SubElement(k, "when").text = str(when)
                ET.SubElement(k, "value").text = f"{sc:.4f}"
        elif pid == "rotation":
            v.text = str(rotation)
        elif pid == "center" and v.find("horiz") is not None:
            v.find("horiz").text, v.find("vert").text = f"{horiz:.6f}", "0"
    return f


def al_filter(tpl, keys):
    """keys: [(music source frame, linear level)]"""
    f = copy.deepcopy(tpl)
    p = next(p for p in f.iter("parameter") if p.findtext("parameterid") == "level")
    for kf in p.findall("keyframe"):
        p.remove(kf)
    p.find("value").text = f"{keys[0][1]:.6f}"
    for when, lv in keys:
        k = ET.SubElement(p, "keyframe")
        ET.SubElement(k, "when").text = str(when)
        ET.SubElement(k, "value").text = f"{lv:.6f}"
    return f


def rate_el():
    r = ET.Element("rate")
    ET.SubElement(r, "timebase").text = "30"
    ET.SubElement(r, "ntsc").text = "TRUE"
    return r


def motion(s, scale):
    """Basic Motion for a shot: (scale %, centre offset, zoom keys). The crop centre cx lands mid-frame, clamped so
    the picture still covers 1080 wide at the smallest scale the shot reaches."""
    z = s.get("zoom")
    lo = min(z) if z else scale
    wd = s["dw"] * s["fit"] * lo / 100  # picture width in sequence pixels
    off = max(-(wd - VW) / 2, min((wd - VW) / 2, (0.5 - s.get("cx", 0.5)) * wd))
    f = s.get("fit", 1.0)
    keys = [(s["in_f"], z[0] * f), (s["in_f"] + s["len"], z[1] * f)] if z else None
    return (z[0] if z else scale) * f, off / VW, keys


def build_xml(reel, segs, total, cams, music_path, music_info, music_at, levels, tpl, counter, title=(), caps=()):
    bm_t, al_t = tpl
    seq = ET.Element("sequence", id=f"seq-{reel['id']}")
    ET.SubElement(seq, "name").text = reel["id"]
    ET.SubElement(seq, "duration").text = str(total)
    seq.append(rate_el())
    tc = ET.SubElement(seq, "timecode")
    tc.append(rate_el())
    ET.SubElement(tc, "string").text = "00:00:00;00"
    ET.SubElement(tc, "frame").text = "0"
    ET.SubElement(tc, "displayformat").text = "NDF"
    med = ET.SubElement(seq, "media")
    vid = ET.SubElement(med, "video")
    fmt = ET.SubElement(ET.SubElement(vid, "format"), "samplecharacteristics")
    fmt.append(rate_el())
    for k, v in (("width", VW), ("height", VH), ("pixelaspectratio", "square"), ("fielddominance", "none")):
        ET.SubElement(fmt, k).text = str(v)
    aud = ET.SubElement(med, "audio")
    ET.SubElement(aud, "numOutputChannels").text = "2"
    afmt = ET.SubElement(ET.SubElement(aud, "format"), "samplecharacteristics")
    ET.SubElement(afmt, "depth").text = "16"
    ET.SubElement(afmt, "samplerate").text = "48000"

    used = set()

    def file_el(key, path, info, kind):
        fe = ET.Element("file", id=f"file-{key}")
        if key in used:
            return fe
        used.add(key)
        ET.SubElement(fe, "name").text = Path(path).name
        ET.SubElement(fe, "pathurl").text = pathurl(path)
        fe.append(rate_el())
        ET.SubElement(fe, "duration").text = str(STILL_DUR if kind == "still" else fr(info["duration"]))
        m = ET.SubElement(fe, "media")
        if kind in ("video", "still"):  # camera: coded size; Premiere applies the rotation tag
            sc = ET.SubElement(ET.SubElement(m, "video"), "samplecharacteristics")
            w, h = (VW, VH) if kind == "still" else (info["video"]["width"], info["video"]["height"])
            ET.SubElement(sc, "width").text = str(w)
            ET.SubElement(sc, "height").text = str(h)
        if kind != "still":
            a = ET.SubElement(m, "audio")
            sc = ET.SubElement(a, "samplecharacteristics")
            ET.SubElement(sc, "depth").text = "16"
            ET.SubElement(sc, "samplerate").text = str(info.get("audio", {}).get("sample_rate", 48000))
            ET.SubElement(a, "channelcount").text = "2"
        return fe

    def clip(cid, key, path, info, start, length, inp, kind, track_idx=None, filt=None):
        c = ET.Element("clipitem", id=cid)
        ET.SubElement(c, "masterclipid").text = f"mc-{key}"
        ET.SubElement(c, "name").text = Path(path).name
        ET.SubElement(c, "enabled").text = "TRUE"
        ET.SubElement(c, "duration").text = str(STILL_DUR if kind == "still" else fr(info["duration"]))
        c.append(rate_el())
        for k, v in (("start", start), ("end", start + length), ("in", inp), ("out", inp + length)):
            ET.SubElement(c, k).text = str(v)
        c.append(file_el(key, path, info, kind))
        if track_idx:
            st = ET.SubElement(c, "sourcetrack")
            ET.SubElement(st, "mediatype").text = "audio"
            ET.SubElement(st, "trackindex").text = str(track_idx)
        if filt is not None:
            c.append(filt)
        return c

    def track(parent, items):
        tr = ET.SubElement(parent, "track")
        for it in items:
            tr.append(it)
        ET.SubElement(tr, "enabled").text = "TRUE"
        ET.SubElement(tr, "locked").text = "FALSE"
        return tr

    v1, a1, a2 = [], [], []
    for i, s in enumerate(segs):
        path, info = cams[s["clip"]]
        inp = s["in_f"]
        v1.append(clip(f"v-{i}", s["clip"], path, info, s["start"], s["len"], inp, "video",
                       filt=bm_filter(bm_t, *(lambda m: (m[0], s.get("rot", 0), m[1], m[2]))(motion(s, seg_scale(s))))))
        if s["kind"] == "react":  # Avery's voice off camera: picture only, music carries it
            continue
        a1.append(clip(f"a1-{i}", s["clip"], path, info, s["start"], s["len"], inp, "audio", track_idx=1))
        a2.append(clip(f"a2-{i}", s["clip"], path, info, s["start"], s["len"], inp, "audio", track_idx=2))
    track(vid, v1)
    bl = []  # V2: b-roll cutaways over dialogue (picture only; the audio stays on the V1 clip's tracks)
    for i, s in enumerate(segs):
        for j, b in enumerate(s.get("broll_frames", [])):
            bpath, binfo = cams[b["clip"]]
            bl.append(clip(f"b-{i}-{j}", b["clip"], bpath, binfo, s["start"] + b["a"], b["e"] - b["a"], fr(b["src"]),
                           "video", filt=bm_filter(bm_t, *(lambda m: (m[0], b["rot"], m[1]))(motion(dict(b, in_f=fr(b["src"]), len=b["e"] - b["a"]), 100.0)))))
    if bl:
        track(vid, bl)
    if counter:
        track(vid, [clip(f"sc-{i}", Path(p).stem, str(p), {}, a, b - a, 0, "still")
                    for i, (p, a, b) in enumerate(counter)])
    if title:
        track(vid, [clip(f"tc-{i}", Path(p).stem, str(p), {}, a, b - a, 0, "still")
                    for i, (p, a, b) in enumerate(title)])
    if caps:
        track(vid, [clip(f"cap-{i}", f"cap_{reel['id']}_{i:03d}", str(p), {}, a, b - a, 0, "still")
                    for i, (p, a, b) in enumerate(caps)])
    track(aud, a1)
    track(aud, a2)

    m_in = fr(music_at)
    keys = [(m_in + t, lv) for t, lv in levels]
    for ch in (1, 2):
        mc = clip(f"m{ch}", "music", music_path, music_info, 0, total, m_in, "audio", track_idx=ch,
                  filt=al_filter(al_t, keys))
        track(aud, [mc])

    root = ET.Element("xmeml", version="4")
    root.append(seq)
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode") + "\n"


def level_keys(segs, music_db):
    """Music level keyframes on the reel timeline (frames), 6-frame ramps at segment-kind changes."""
    keys = []
    for s in segs:
        lv = db_to_lin(music_db.get(s["kind"], music_db["talk"]))
        if not keys:
            keys.append((0, lv))
        elif abs(keys[-1][1] - lv) > 1e-6:
            keys.append((s["start"], keys[-1][1]))
            keys.append((s["start"] + 6, lv))
    keys.append((segs[-1]["start"] + segs[-1]["len"], keys[-1][1]))
    return keys


# ---------- preview ----------

def render_preview(segs, cams, music_path, music_at, keys, total, cfg, counter, out_mp4, tmp):
    tmp.mkdir(parents=True, exist_ok=True)
    def look_for(clip):
        """LUT + finish for one clip. clip_lut maps a clip stem to its own cube, or to none (not Log footage)."""
        name = (cfg.get("clip_lut") or {}).get(clip, cfg.get("lut"))
        if not name or str(name).lower() == "none":
            return cfg.get("finish") or "null"
        lut = Path(name).expanduser()
        if not lut.is_absolute():  # plans name repo cubes as luts/<name>.cube
            lut = Path(__file__).resolve().parents[1] / lut
        return f"lut3d=file='{lut}':interp=tetrahedral,{cfg.get('finish') or 'null'}"

    turn = {0: "null", -90: "transpose=2", 90: "transpose=1", 180: "hflip,vflip"}
    parts = []
    for i, s in enumerate(segs):
        path, _ = cams[s["clip"]]
        scale = seg_scale(s) / 100
        sw, sh = int(round(VW * scale / 2) * 2), int(round(VH * scale / 2) * 2)
        # every piece leaves in TV range: Canon MP4s are full range, iPhone TV, and the stream-copy concat below
        # breaks (drops a piece's picture) when the parts disagree
        # zero each piece's timestamps and pin audio to the video length: HEVC seeks can start a frame late,
        # which drops a frame and slips sync at the concat seams
        if s.get("zoom"):  # slow push: scale ramps z0 -> z1 over the shot (fill size times the zoom)
            z0, z1 = s["zoom"]
            bw, bh = s["dw"] * s["fit"], s["dh"] * s["fit"]
            zt = f"({z0}+({z1}-{z0})*t/{s['len'] / FPS:.4f})/100"
            size = f"scale=w='2*trunc({bw:.1f}*{zt}/2)':h='2*trunc({bh:.1f}*{zt}/2)':eval=frame:out_range=tv"
        else:
            size = f"scale={sw}:{sh}:force_original_aspect_ratio=increase:out_range=tv"
        vf = (f"setpts=PTS-STARTPTS,{look_for(s['clip'])},{turn[s.get('rot', 0)]},{size},"
              f"crop={VW}:{VH}:{crop_x(s.get('cx', 0.5))},setsar=1,fps=30000/1001,format=yuv420p")
        af = (f"{'volume=0' if s['kind'] == 'react' else 'anull'},asetpts=PTS-STARTPTS,"
              f"apad,atrim=duration={s['len'] / FPS:.6f}")
        part = tmp / f"seg{i:02d}.mov"
        ins, fc, last = ["-ss", f"{s['in_f'] / FPS:.4f}", "-i", path], f"[0:v]{vf}[v0];[0:a]{af}[a]", "v0"
        for k, b in enumerate(s.get("broll_frames", []), 1):  # cutaway: b-roll picture over this segment's audio
            at, dur = b["a"] / FPS, (b["e"] - b["a"]) / FPS
            ins += ["-ss", f"{b['src']:.4f}", "-t", f"{dur + 0.1:.4f}", "-i", cams[b["clip"]][0]]
            fc += (f";[{k}:v]setpts=PTS-STARTPTS,{look_for(b['clip'])},{turn[b['rot']]},scale={VW}:{VH}:force_original_aspect_ratio=increase:out_range=tv,"
                   f"crop={VW}:{VH}:{crop_x(b.get('cx', 0.5))},setsar=1,fps=30000/1001,format=yuv420p,setpts=PTS+{at:.4f}/TB[b{k}];"
                   f"[{last}][b{k}]overlay=eof_action=pass:enable='gte(n,{b['a']})*lt(n,{b['e']})'[v{k}]")
            last = f"v{k}"
        subprocess.run([media.FFMPEG, "-v", "error", "-y", *ins, "-filter_complex", fc,
                        "-map", f"[{last}]", "-map", "[a]", "-frames:v", str(s["len"]),
                        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(part)], check=True)
        parts.append(part)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    body = tmp / "body.mov"
    subprocess.run([media.FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(body)], check=True)
    pts = [(f / FPS, lv) for f, lv in keys]
    expr = f"{pts[-1][1]:.6f}"
    for (t0, l0), (t1, l1) in reversed(list(zip(pts[:-1], pts[1:]))):
        if t1 - t0 < 1e-6:
            continue
        expr = f"if(lt(t,{t1:.4f}),({l0:.6f}+({l1:.6f}-{l0:.6f})*(t-{t0:.4f})/{t1 - t0:.4f}),{expr})"
    T = total / FPS
    ins = ["-i", str(body), "-i", str(music_path)]
    vchain, last = "", "0:v"
    for k, (png, a, b) in enumerate(counter):
        ins += ["-i", str(png)]  # one frame, held by eof_action=repeat: a looped input re-decodes the PNG every frame
        lab = f"v{k}"
        vchain += (f"[{last}][{k + 2}:v]overlay=0:0:eof_action=repeat:"
                   f"enable='between(t,{a / FPS:.4f},{b / FPS - 0.001:.4f})'[{lab}];")
        last = lab
    fc = (vchain +
          f"[1:a]atrim=start={music_at:.4f}:duration={T:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
          f"volume='{expr}':eval=frame,afade=t=out:st={T - 0.8:.3f}:d=0.8[m];"
          f"[0:a][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1:LRA=11,aresample=48000[a]")
    vmap = f"[{last}]" if counter else "0:v"
    vcodec = ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"] if counter else ["-c:v", "copy"]
    subprocess.run([media.FFMPEG, "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", vmap, "-map", "[a]",
                    *vcodec, "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out_mp4)], check=True)


# ---------- run ----------

def run(plan_yaml, ids=None, preview=False):
    cfg = yaml.safe_load(Path(plan_yaml).read_text())
    shoot = Path(cfg["shoot"])
    work = Path(cfg["work"]).expanduser()
    out_dir = work / "cuts"
    out_dir.mkdir(parents=True, exist_ok=True)
    tpl = template_filters(cfg["template_xml"])

    for reel in cfg["reels"]:
        if ids and reel["id"] not in ids:
            continue
        segs = []
        for c, a, b, k, *opt in reel["segments"]:  # optional 5th value: scale (%) or {scale, end}
            o = opt[0] if opt else {}
            o = {"scale": float(o)} if isinstance(o, (int, float)) else dict(o)
            segs.append(dict(clip=c, inp=float(a), out=float(b), kind=k, **o))
        stems = sorted({s["clip"] for s in segs})
        words = {st: load_words(work, st) for st in stems}
        cams = {}
        for st in stems + sorted({b[0] for s in segs for b in s.get("broll", [])} - set(stems)):
            p = next((shoot / "RAW VIDEO").glob(f"{st}.*"))
            cams[st] = (str(p), media.summarize(p))

        def geom(clip):
            """rotate: Premiere degrees for footage shot vertical without a rotation tag (-90 = counter-clockwise).
            fit scales Basic Motion so the rotated frame fills 1080x1920 (1.0 for 1080p, 0.5 for 4K)."""
            rot = int(cfg.get("rotate", 0))
            v = cams[clip][1]["video"]
            w, h = (v["height"], v["width"]) if abs(v.get("rotation", 0)) % 180 == 90 else (v["width"], v["height"])
            if rot in (90, -90):
                w, h = h, w
            return dict(rot=rot, fit=max(VW / w, VH / h), dw=w, dh=h)  # dw x dh: the frame as it plays, before fit

        def centre(d, clip, t0, t1):
            """x: crop centre (0-1) from the plan; else wide shots crop on the faces, centred when there are none."""
            if "x" in d:
                d["cx"] = float(d.pop("x"))
            elif d["dw"] / d["dh"] > VW / VH + 0.01:
                d["cx"] = face_cx(cams[clip][0], t0, t1, d["rot"]) or 0.5
            return d

        levels = {}
        for s in segs:
            if s["clip"] not in levels:  # voice level per 10 ms, from the 16 kHz cache `palefire transcribe` made
                x = media.extract_audio(cams[s["clip"]][0], work / "audio", sr=ASR_SR)
                levels[s["clip"]] = band_levels(x)
            resolve(s, words[s["clip"]], cams[s["clip"]][1]["duration"], levels[s["clip"]])
            s.update(geom(s["clip"]))
            centre(s, s["clip"], s["inp"], s["out"])
            # broll: [[clip, source s, at s into this segment, dur s, (crop centre x)]] cutaways over this segment's audio
            s["broll_items"] = [centre(dict(clip=c, src=float(t), at=float(at), dur=float(d), **geom(c), **({"x": x[0]} if x else {})),
                                       c, float(t), float(t) + float(d))
                                for c, t, at, d, *x in s.get("broll", [])]
        music_path = shoot / "music" / reel["music"]
        beats_path = work / "music" / (Path(reel["music"]).stem + ".beats.json")
        if not music_path.exists():  # not in the shoot folder: take it from the shared library (palefire music)
            from .music import lookup
            hit = lookup(reel["music"])
            if not hit:
                raise SystemExit(f"{reel['music']}: not in {shoot / 'music'} and not in the music index "
                                 f"(run `palefire music index`)")
            music_path, beats_path = hit
        music_info = media.summarize(music_path)
        bj = json.loads(beats_path.read_text())
        beats = bj["beats"]

        if "payoff" in reel:  # the YAML's break time is approximate: use the real downbeat nearest to it
            reel = dict(reel, break_at=min(bj["downbeats"], key=lambda d: abs(d - reel["break_at"])))
            music_at = reel["break_at"] - sum(s["out"] - s["inp"] for s in segs[:reel["payoff"]])
        else:
            music_at = float(reel.get("music_at", 0.0))
        join_takes(segs)
        snap_plan(segs, beats, music_at, cfg.get("snap_window", 0.30))
        total = layout(segs)
        if "payoff" in reel:  # shift the grid so the payoff starts on the break (whole beats after snapping)
            music_at = reel["break_at"] - segs[reel["payoff"]]["start"] / FPS
        if music_at < 0:
            raise SystemExit(f"{reel['id']}: reel runs longer before the payoff than the track before its break")
        broll_frames(segs)
        fail, warn = checks(segs, cams)
        for line in warn:
            print(f"  CHECK  {line}")
        if fail:
            raise SystemExit(f"{reel['id']}: frame checks failed, nothing written:\n  " + "\n  ".join(fail))

        counter = counter_states(reel, segs, total, out_dir)
        title = title_states(reel, segs, out_dir)
        keys = level_keys(segs, cfg["music_db"])
        cards = captions(segs, words, cfg.get("fix"))
        caps = caption_states(reel, cards, out_dir)
        xml = build_xml(reel, segs, total, cams, music_path, music_info, music_at, keys, tpl, counter, title, caps)
        ET.fromstring(xml.split("\n", 2)[2])
        (out_dir / f"{reel['id']}.xml").write_text(xml)
        (out_dir / f"{reel['id']}.srt").write_text(srt(cards))

        on_beat, t = 0, 0.0
        for s in segs[:-1]:
            t += s["len"] / FPS
            if min(abs(b - (t + music_at)) for b in beats) < 0.045:
                on_beat += 1
        shots = sorted(s["len"] / FPS for s in segs)
        print(f"\n{reel['id']}: {reel['title']}")
        print(f"  {total / FPS:.1f} s, {len(segs)} shots, median shot {shots[len(shots) // 2]:.2f} s, "
              f"longest {shots[-1]:.2f} s, {on_beat}/{len(segs) - 1} cuts on a beat")
        print(f"  music: {reel['music']} from {music_at:.2f} s ({bj['bpm']} BPM)")
        if counter:
            print("  counter: " + ", ".join(f"{Path(p).stem.split('_score_')[1]} @ {a / FPS:.1f}s" for p, a, _ in counter))
        print(f"  xml: {out_dir / (reel['id'] + '.xml')}\n  srt: {out_dir / (reel['id'] + '.srt')} ({len(cards)} cards)")
        if preview:
            mp4 = out_dir / f"{reel['id']}_preview.mp4"
            render_preview(segs, cams, music_path, music_at, keys, total, cfg, counter + title + caps, mp4, work / "tmp" / reel["id"])
            print(f"  preview: {mp4}")
