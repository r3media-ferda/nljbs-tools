"""`palefire music index|pick`: a shared music library that reels pick from.

Library: one folder per vibe, Epidemic names kept as downloaded, e.g.
  /Volumes/Extreme SSD/MUSIC LIBRARY/party-upbeat/ES_Toffee - Lukas Got Lucky.mp3
The folder name is the track's tag. Add tracks any time and re-run `index`; only new tracks are analyzed.

index -> music/beats/<stem>.beats.json  (in the repo; same format `palefire beats` writes; `palefire cut` reads it)
         music/index.json               one entry per track: tag, title, artist, duration, bpm, beat steadiness,
                                        loudness, intro length, breaks and lifts, and its path inside the library
The index lives in the git repo so any session (this Mac, Oz's, a cloud session) can pick tracks without the audio.
The audio lives in a shared folder; music/library.yaml lists where it can be, first one found wins.
pick  -> ranks tracks for a reel: tag, tempo range, enough length, a break to land the payoff on, and not used
         for the same client recently (usage comes from the music: lines in shoots/*.yaml, so it needs no upkeep).
Reads the library, writes only to the repo's music/ folder.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import yaml

from nljbs import media

from .beats import BEAT_PY

AUDIO = {".mp3", ".wav", ".aif", ".aiff", ".m4a"}
REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "music"


def library_root():
    """The shared library folder on this machine: $R3_MUSIC, else the first folder in music/library.yaml that exists."""
    if os.environ.get("R3_MUSIC"):
        return Path(os.environ["R3_MUSIC"]).expanduser()
    roots = (yaml.safe_load((STORE / "library.yaml").read_text()) or {}).get("roots", [])
    for r in roots:
        if Path(r).expanduser().is_dir():
            return Path(r).expanduser()
    raise SystemExit("music library not found: mount it or add its folder to music/library.yaml (roots:)")


def tracks(library):
    return sorted(p for p in Path(library).rglob("*") if p.suffix.lower() in AUDIO and not p.name.startswith("."))


def title_artist(stem):
    m = re.match(r"(?:ES_)?(.*?)\s+-\s+(.*)$", stem)
    return (m.group(1), m.group(2)) if m else (stem, "")


def lufs(path):
    r = subprocess.run([media.FFMPEG, "-nostdin", "-v", "info", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def shape(beats):
    """Intro length, breaks (a bar 4+ dB under the median after a body bar) and lifts (back up after a break)."""
    bars = beats["bars"]
    if len(bars) < 4:
        return 0.0, [], []
    db = np.array([b["db"] for b in bars])
    med = np.median(db)
    intro = next((b["t"] for b, d in zip(bars, db) if d >= med - 2), 0.0)
    breaks, lifts, low = [], [], False
    for i in range(1, len(bars)):
        if not low and db[i] < med - 4 and db[i - 1] >= med - 2 and bars[i]["t"] > intro + 4:
            breaks.append(bars[i]["t"])
            low = True
        elif low and db[i] >= med - 1:
            lifts.append(bars[i]["t"])
            low = False
    end = beats["duration"] - 15  # a drop in the last bars is the song ending, not a break to cut on
    return (round(float(intro), 2), [round(t, 2) for t in breaks if t < end],
            [round(t, 2) for t in lifts if t < end])


def run_index(library=None, force=False):
    library = Path(library).expanduser() if library else library_root()
    if not library.is_dir():
        raise SystemExit(f"{library}: not found (is the drive mounted?)")
    beats_dir = STORE / "beats"
    beats_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which(media.FFMPEG) or media.FFMPEG
    worker = str(Path(__file__).with_name("beats_worker.py"))
    for folder in sorted({p.parent for p in tracks(library)}):  # Beat This once per folder, new tracks only
        r = subprocess.run([BEAT_PY, worker, ffmpeg, str(folder), str(beats_dir)] + (["--force"] if force else []),
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"Beat This failed under {BEAT_PY} on {folder.name}:\n{r.stderr[-800:]}")

    old = {e["file"]: e for e in json.loads((STORE / "index.json").read_text())} if (STORE / "index.json").exists() else {}
    index = []
    for p in tracks(library):
        b = json.loads((beats_dir / f"{p.stem}.beats.json").read_text())
        prev = old.get(p.name)
        rel = str(p.relative_to(library))
        if prev and not force and prev.get("rel") == rel:
            index.append(prev)
            continue
        title, artist = title_artist(p.stem)
        intro, breaks, lifts = shape(b)
        index.append(dict(file=p.name, rel=rel, tag=p.parent.name, title=title, artist=artist,
                          duration=b["duration"], bpm=b["bpm"], beat_jitter=b["beat_jitter"], lufs=lufs(p),
                          intro=intro, breaks=breaks, lifts=lifts, indexed=dt.date.today().isoformat()))
    (STORE / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(index)} tracks indexed -> {STORE / 'index.json'}\n")
    print(f"  {'tag':16} {'bpm':>5} {'len':>5} {'beat':>6} {'intro':>5}  breaks      track")
    for e in sorted(index, key=lambda e: (e["tag"], e["bpm"])):
        steady = "steady" if e["beat_jitter"] < 0.08 else "loose"
        brk = ",".join(f"{t:.0f}" for t in e["breaks"][:3]) or "-"
        print(f"  {e['tag']:16} {e['bpm']:5.1f} {e['duration']:5.0f} {steady:>6} {e['intro']:5.1f}  {brk:11} "
              f"{e['title']} ({e['artist']})")


def usage():
    """{track file name: [(client folder, shoot date)]} from every shoots/*.yaml plan."""
    used = {}
    for plan in sorted((REPO / "shoots").glob("*.yaml")):
        cfg = yaml.safe_load(plan.read_text()) or {}
        shoot = str(cfg.get("shoot", ""))
        client = next((part for part in Path(shoot).parts if part.isupper() and len(part) > 3), "")
        try:
            date = dt.date.fromisoformat(plan.stem[:10])
        except ValueError:
            date = None
        for reel in cfg.get("reels", []):
            m = reel.get("music")
            if m:
                used.setdefault(Path(m).name, []).append((client, date))
    return used


def lookup(name):
    """(library path, beats file) for a `music:` value given as file name, stem, or title; None if not indexed."""
    idx = STORE / "index.json"
    if not idx.exists():
        return None
    key = Path(name).stem.lower()
    for e in json.loads(idx.read_text()):
        if key in (Path(e["file"]).stem.lower(), e["title"].lower()):
            return library_root() / e["rel"], STORE / "beats" / f"{Path(e['file']).stem}.beats.json"
    return None


def run_pick(tag=None, bpm=None, min_len=60.0, client=None, days=60, need_break=False, top=5):
    idx = STORE / "index.json"
    if not idx.exists():
        raise SystemExit("no index yet: run `palefire music index` first")
    lo, hi = map(float, bpm.split("-")) if bpm else (0, 999)
    used = usage()
    today = dt.date.today()
    rows = []
    for e in json.loads(idx.read_text()):
        if tag and e["tag"] != tag:
            continue
        # Beat This sometimes counts double time (a 94 BPM groove read as 188), so half the tempo also matches
        if not (lo <= e["bpm"] <= hi or lo <= e["bpm"] / 2 <= hi) or e["duration"] < min_len:
            continue
        if need_break and not e["breaks"]:
            continue
        recent = [d for c, d in used.get(e["file"], []) if client and client.upper() in c.upper()
                  and (d is None or (today - d).days <= days)]
        if recent:
            continue
        score = (2 if e["breaks"] else 0) + (1 if e["beat_jitter"] < 0.08 else 0) - 0.02 * max(0, e["intro"] - 4)
        score -= 0.5 * len(used.get(e["file"], []))  # prefer tracks nobody has used yet
        rows.append((score, e))
    rows.sort(key=lambda r: -r[0])
    if not rows:
        print("no track fits; loosen --bpm or --tag, or add tracks to the library")
        return
    for _, e in rows[:top]:
        brk = ", ".join(f"{t:.0f}s" for t in e["breaks"][:3]) or "none"
        n = len(used.get(e["file"], []))
        print(f"{e['file']}\n   {e['tag']}, {e['bpm']} BPM, {e['duration']:.0f}s, beat "
              f"{'steady' if e['beat_jitter'] < 0.08 else 'loose'}, intro {e['intro']:.0f}s, breaks at {brk}, used {n}x")
