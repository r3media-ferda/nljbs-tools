"""`nljbs screen <episode.yaml>`: OBS screen states -> stable runs + IG image box per run.

Outputs in the work dir:
  obs_diff10.npy   mean abs frame difference at 10 fps (OBS time)
  screen.json      [{"k", "a", "b", "box": [x0,y0,x1,y1] | null}]   a/b = OBS seconds
  screen/NNN.jpg   full-res still per run;  screen/sheet_N.jpg review sheets with boxes drawn
"""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
import yaml

from . import media

FPS_SCAN = 10
SW, SH = 320, 180


def diff_series(obs):
    p = subprocess.Popen([media.FFMPEG, "-v", "error", "-i", str(obs), "-vf",
                          f"fps={FPS_SCAN},scale={SW}:{SH},format=gray", "-f", "rawvideo", "-"],
                         stdout=subprocess.PIPE)
    prev, out = None, []
    while True:
        buf = p.stdout.read(SW * SH)
        if len(buf) < SW * SH:
            break
        f = np.frombuffer(buf, np.uint8).astype(np.int16)
        out.append(0.0 if prev is None else float(np.abs(f - prev).mean()))
        prev = f
    p.wait()
    return np.array(out, np.float32)


def stable_runs(d, thr=0.6, min_len=0.6):
    """Runs where the screen holds still (diff < thr) for at least min_len seconds."""
    still = d < thr
    runs, i = [], 0
    while i < len(still):
        if still[i]:
            j = i
            while j < len(still) and still[j]:
                j += 1
            if (j - i) / FPS_SCAN >= min_len:
                runs.append([i / FPS_SCAN, j / FPS_SCAN])
            i = j
        else:
            i += 1
    return runs


def detect_box(im):
    """Largest image-like rectangle below the browser chrome (legacy boxdet det + expand)."""
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H, W = g.shape
    y0 = 95
    m = cv2.blur(g, (9, 9))
    sd = np.sqrt(np.maximum(cv2.blur(g * g, (9, 9)) - m * m, 0))
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    img = ((sd > 5) | (g > 75) | ((hsv[..., 1] > 60) & (g > 35))).astype(np.float32)
    img[:y0] = 0

    def longest(mask, lo=0):
        best, i, n = (0, 0), lo, len(mask)
        while i < n:
            if mask[i]:
                j = i
                while j < n and mask[j]:
                    j += 1
                if j - i > best[1] - best[0]:
                    best = (i, j)
                i = j
            else:
                i += 1
        return best

    col = np.convolve(img[y0:].mean(0), np.ones(15) / 15, "same")
    x0, x1 = longest(col > 0.55)
    if x1 - x0 < 100:
        return None
    row = np.convolve(img[:, x0:x1].mean(1), np.ones(9) / 9, "same")
    ya, yb = longest(row > 0.55, y0)
    if yb - ya < 100:
        return None
    return trim_box(g, [int(x0), int(ya), int(x1), int(yb)])


def trim_box(g, box, hi=232, lo=30, max_frac=0.3):
    """Shave white/black letterbox bars off the box edges (IG pads non-square posts)."""
    x0, y0, x1, y1 = box

    def keep(means):
        """Longest run of non-flat lines; give up if it would drop more than max_frac per side."""
        ok = ~((means > hi) | (means < lo))
        best, i, n = (0, n0 := len(ok)), 0, len(ok)
        best = (0, 0)
        while i < n:
            if ok[i]:
                j = i
                while j < n and ok[j]: j += 1
                if j - i > best[1] - best[0]: best = (i, j)
                i = j
            else:
                i += 1
        a, b = best
        if b - a < 50 or a > n * max_frac or n - b > n * max_frac:
            return 0, n
        return a, b

    a, b = keep(g[y0:y1, x0:x1].mean(0)); x0, x1 = x0 + a, x0 + b
    a, b = keep(g[y0:y1, x0:x1].mean(1)); y0, y1 = y0 + a, y0 + b
    return [x0, y0, x1, y1]


def run(episode_yaml):
    ep = yaml.safe_load(Path(episode_yaml).read_text())
    work = Path(ep["work_dir"])
    obs = ep["obs"][0]
    d_path = work / "obs_diff10.npy"
    if d_path.exists():
        d = np.load(d_path)
    else:
        print("Scanning OBS at 10 fps…", flush=True)
        d = diff_series(obs)
        np.save(d_path, d)
    runs = stable_runs(d)
    sdir = work / "screen"
    sdir.mkdir(exist_ok=True)
    out, tiles = [], []
    for k, (a, b) in enumerate(runs):
        jpg = sdir / f"{k:03d}.jpg"
        if not jpg.exists():
            subprocess.run([media.FFMPEG, "-v", "error", "-y", "-ss", f"{(a + b) / 2:.2f}", "-i", str(obs),
                            "-frames:v", "1", "-q:v", "3", str(jpg)], check=True)
        im = cv2.imread(str(jpg))
        box = detect_box(im)
        out.append({"k": k, "a": round(a, 2), "b": round(b, 2), "box": box})
        t = cv2.resize(im, (480, 270))
        if box:
            cv2.rectangle(t, (box[0] // 4, box[1] // 4), (box[2] // 4, box[3] // 4), (0, 255, 0), 2)
        cv2.putText(t, f"#{k} {a:.0f}-{b:.0f}s", (4, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        tiles.append(t)
    (work / "screen.json").write_text(json.dumps(out, indent=0))
    for s in range(0, len(tiles), 20):
        g = tiles[s:s + 20] + [np.zeros((270, 480, 3), np.uint8)] * (20 - len(tiles[s:s + 20]))
        cv2.imwrite(str(sdir / f"sheet_{s // 20}.jpg"),
                    np.vstack([np.hstack(g[r * 4:r * 4 + 4]) for r in range(5)]), [cv2.IMWRITE_JPEG_QUALITY, 72])
    print(f"{len(runs)} stable screen states; sheets in {sdir}")
