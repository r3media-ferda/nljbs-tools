"""Beat This on each track in a folder. Run by `palefire beats` under the Python that has beat_this + torch.

usage: python3.15 beats_worker.py <ffmpeg> <music folder> <out dir> [--force]
Writes <out>/<track>.beats.json: tempo, beats, downbeats, per-bar loudness. Prints a section map per track.
Beat This's own file loader needs torchcodec/soundfile, so audio is decoded with ffmpeg and fed to Audio2Beats.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from beat_this.inference import Audio2Beats

FFMPEG, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
force = "--force" in sys.argv[4:]
out.mkdir(parents=True, exist_ok=True)

try:
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cpu"
except Exception:
    device = "cpu"
a2b = Audio2Beats(checkpoint_path="final0", device=device, dbn=False)


def decode(path, sr=22050):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32), sr


for p in sorted(src.iterdir()):
    if p.name.startswith(".") or p.suffix.lower() not in (".mp3", ".wav", ".aif", ".aiff", ".m4a"):
        continue
    dst = out / (p.stem + ".beats.json")
    if dst.exists() and not force:
        print(f"\n{p.name}: kept existing beats (--force to redo)")
        continue
    y, sr = decode(p)
    beats, downbeats = a2b(y.copy(), sr)
    beats, downbeats = np.asarray(beats), np.asarray(downbeats)
    ibi = np.diff(beats)
    bpm = 60 / np.median(ibi) if len(ibi) else 0
    steady = float(np.std(ibi) / np.mean(ibi)) if len(ibi) else 0
    bars = []
    for a, b in zip(downbeats, list(downbeats[1:]) + [len(y) / sr]):
        seg = y[int(a * sr):int(b * sr)]
        db = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9) if len(seg) else -99
        bars.append({"t": round(float(a), 3), "db": round(float(db), 1)})
    rec = {"file": p.name, "duration": round(len(y) / sr, 2), "bpm": round(float(bpm), 1),
           "beat_jitter": round(steady, 3), "beats": [round(float(b), 3) for b in beats],
           "downbeats": [round(float(d), 3) for d in downbeats], "bars": bars}
    dst.write_text(json.dumps(rec, indent=1))

    dbs = np.array([b["db"] for b in bars])
    med = np.median(dbs) if len(dbs) else 0

    def tag(v):  # DROP > 4 dB under the median bar, PEAK > 2 dB over: where the breaks and lifts are
        return "DROP" if v < med - 4 else "PEAK" if v > med + 2 else "body"

    marks, start = [], 0
    for i in range(1, len(bars) + 1):
        if i == len(bars) or tag(dbs[i]) != tag(dbs[start]):
            marks.append(f"{bars[start]['t']:6.1f}s {tag(dbs[start]):4} x{i - start:<2}")
            start = i
    bar_s = np.median(np.diff(downbeats)) if len(downbeats) > 1 else 0
    print(f"\n{p.name}\n  {rec['duration']:.0f}s  {rec['bpm']} BPM  beat jitter {rec['beat_jitter']}  "
          f"{len(beats)} beats  {len(downbeats)} bars (bar = {bar_s:.2f}s)")
    print("  sections: " + " | ".join(marks))
