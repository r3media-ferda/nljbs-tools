"""Measure Avery's finished short-form exports: cut rhythm, openings, endings, loudness.

Produced the numbers in docs/R3_SHORT_FORM_STYLE.md. Re-run when the house style needs re-measuring.
usage: .venv/bin/python scripts/style_measure.py [inventory.json] [measurements.json]

Sets (from inventory.json):
  avery  - Premiere/Media Encoder exports ("Mainconcept Video"), vertical, <= 120 s
  tool   - Reels Archive exports written by an ffmpeg-based clipper ("Lavf" + VideoHandler)
Reads ~/r3-work/style/inventory.json and writes measurements.json there. Reads the drives, writes nothing to them.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import static_ffmpeg

static_ffmpeg.add_paths(weak=True)
# Shot detection comes from the ECC plugin's taste-distillation skill (affaan-m/ECC), which wraps PySceneDetect.
TASTE = Path.home() / ".claude/plugins/marketplaces/ecc/skills/taste-distillation/scripts"
if not TASTE.is_dir():
    raise SystemExit(f"{TASTE} missing: install the ECC plugin in Claude Code (/plugin marketplace add affaan-m/ECC)")
sys.path.insert(0, str(TASTE))
from taste.cadence import detect  # adaptive-threshold PySceneDetect sweep

# Work files (inventory.json in, measurements.json out) live in ~/r3-work/style, not in the repo.
HERE = Path.home() / "r3-work" / "style"

INV = HERE / (sys.argv[1] if len(sys.argv) > 1 else "inventory.json")
OUT = HERE / (sys.argv[2] if len(sys.argv) > 2 else "measurements.json")
inv = json.load(open(INV))


def pick_sets():
    sets = {"avery": [], "tool": []}
    seen = set()
    for x in inv:
        if "err" in x or x["h"] <= x["w"] or x["dur"] > 120:
            continue
        key = (x["dur"], x["size_mb"])
        if key in seen:  # "(1)" / "_1" duplicates
            continue
        seen.add(key)
        # Premiere's handler name carries a leading \x1f, so match anywhere in it.
        if "Mainconcept" in x["handler"]:
            sets["avery"].append(x)
        elif x["encoder"].startswith("Lavf"):
            sets["tool"].append(x)  # OpusClip output per Avery: not measured
    return {"avery": sets["avery"]}


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    return (float(i.group(1)) if i else None, float(p.group(1)) if p else None)


def main():
    sets = pick_sets()
    out = []
    for name, items in sets.items():
        for n, x in enumerate(items, 1):
            print(f"[{name} {n}/{len(items)}] {x['file']}", flush=True)
            try:
                c = detect(x["path"])
            except Exception as e:
                print("   skip:", e)
                continue
            shots = [s["duration"] for s in c.shots]
            cuts = [s["start"] for s in c.shots[1:]]
            lufs, peak = loudness(x["path"])
            out.append({
                "set": name, "file": x["file"], "dur": x["dur"], "fps": x["fps"], "mtime": x["mtime"],
                "n_shots": c.n_shots, "median_shot": c.median_shot, "mean_shot": c.mean_shot,
                "cuts_per_min": c.cuts_per_min, "rhythm_var": c.rhythm_variance,
                "first_cut": cuts[0] if cuts else None,
                "cuts_first3s": sum(1 for t in cuts if t < 3.0),
                "last_shot": shots[-1] if shots else None,
                "longest_shot": max(shots) if shots else None,
                "shots": [round(s, 3) for s in shots],
                "lufs": lufs, "peak": peak,
            })
            json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
