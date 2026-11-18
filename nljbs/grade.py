"""`nljbs grade <edit.yaml>`: bake each camera's color into a graded copy so the XML arrives colored.

Per camera (edit config `grade:`): Canon LUT via lut3d (+ finish), or a plain filter chain for the Sony.
Encode: Apple VideoToolbox HEVC 10-bit, Rec.709 tagged, limited range; same frame rate and frame count as
the source, so every offset from sync stays valid. Audio re-encoded to AAC for scratch reference.
Render to ~/nljbs-work, verify (frame count + pixel match against the look), then copy to the drive under a
new name (<stem>_GRADED.mp4) and byte-compare. Never overwrites.
"""
import filecmp
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import yaml

from . import media


def chain(g, lut_root):
    parts = []
    if g.get("lut"):
        parts.append(f"lut3d=file='{Path(lut_root) / g['lut']}':interp=tetrahedral")
    if g.get("filters"):
        parts.append(g["filters"])
    return ",".join(parts) or "null"


def frame(src, t, vf):
    raw = subprocess.run([media.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
                          "-vf", f"{vf},scale=480:270", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(270, 480, 3).astype(np.float32)


def nframes(p):
    out = subprocess.run([media.FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=r_frame_rate,nb_read_packets", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout.strip()
    rate, n = out.split(",")
    return rate, int(n)


def run(edit_yaml, deliver=False, only=None):
    E = yaml.safe_load(Path(edit_yaml).read_text())
    ep = yaml.safe_load(Path(os.path.expanduser(E["episode"])).read_text())
    work = Path(ep["work_dir"]) / "graded"; work.mkdir(exist_ok=True)
    rec = Path(ep["recording_folder"])
    G = E["grade"]; lut_root = G["lut_root"]
    cams = {Path(c["file"]).stem: c["file"] for c in ep["cameras"]}
    for stem, g in G["cameras"].items():
        if only and stem not in only:
            continue
        src = Path(cams[stem]); out = work / f"{stem}_GRADED.mp4"; vf = chain(g, lut_root)
        if not out.exists():
            fps = media.summarize(src)["video"]["fps"]
            br = "60M" if fps > 60 else "45M"
            print(f"Grading {src.name} ({fps:.2f} fps, {br})…", flush=True)
            tmp = work / f"{stem}_GRADED.part.mp4"
            subprocess.run([media.FFMPEG, "-v", "error", "-y", "-i", str(src),
                            "-map", "0:v:0", "-map", "0:a:0",
                            "-vf", vf + ",scale=out_range=tv:out_color_matrix=bt709,format=p010le",
                            "-c:v", "hevc_videotoolbox", "-profile:v", "main10", "-b:v", br, "-maxrate", br,
                            "-tag:v", "hvc1", "-color_primaries", "bt709", "-color_trc", "bt709",
                            "-colorspace", "bt709", "-color_range", "tv",
                            "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(tmp)], check=True)
            tmp.rename(out)
        # verify: same frame rate + frame count, and the graded frame matches the look at two times
        r0, n0 = nframes(src); r1, n1 = nframes(out)
        diffs = [float(np.abs(frame(out, t, "null") - frame(src, t, vf)).mean()) for t in (300.0, 900.0)]
        ok = r0 == r1 and abs(n0 - n1) <= 1 and max(diffs) < 6
        print(f"  {out.name}: {out.stat().st_size / 1e9:.1f} GB  rate {r1} (src {r0})  frames {n1} (src {n0})  "
              f"look diff {diffs[0]:.1f}/{diffs[1]:.1f}  {'OK' if ok else 'CHECK'}", flush=True)
        if not ok:
            raise SystemExit(f"verify failed for {out.name}; not delivering")
        if deliver:
            dst = rec / out.name
            if dst.exists():
                print(f"  already on drive: {dst.name} (not overwriting)"); continue
            shutil.copy2(out, dst)
            if not filecmp.cmp(out, dst, shallow=False):
                raise SystemExit(f"copy verify FAILED: {dst}")
            print(f"  delivered {dst}", flush=True)
