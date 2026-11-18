"""`nljbs luts <edit.yaml>`: one finished .cube per camera = Canon LUT + finish (or the Sony match) in a single file.

Avery applies exactly one LUT per camera, as a master-clip Input LUT, and nothing else, so nothing stacks.
Built by running ffmpeg's identity Hald CLUT (level 8 -> 64^3 grid) through the camera's grade chain and
writing the result as a .cube (red varies fastest in both formats). Verified against the filter chain on real frames.
"""
import filecmp
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import yaml

from . import grade, media


def build_cube(vf, out, title, level=8):
    n = level * level; side = level ** 3
    raw = subprocess.run([media.FFMPEG, "-v", "error", "-f", "lavfi", "-i", f"haldclutsrc={level}", "-frames:v", "1",
                          "-vf", f"format=rgb48le,{vf},format=rgb48le", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"],
                         capture_output=True, check=True).stdout
    px = np.frombuffer(raw, np.uint16).reshape(side * side, 3).astype(np.float64) / 65535.0
    with open(out, "w") as f:
        f.write(f'TITLE "{title}"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n')
        np.savetxt(f, px, fmt="%.6f")


def run(edit_yaml, deliver_dir=None):
    E = yaml.safe_load(Path(edit_yaml).read_text())
    ep = yaml.safe_load(Path(os.path.expanduser(E["episode"])).read_text())
    work = Path(ep["work_dir"]) / "luts"; work.mkdir(exist_ok=True)
    G = E["grade"]; cams = {Path(c["file"]).stem: c for c in ep["cameras"]}
    made = []
    for stem, g in G["cameras"].items():
        label = g.get("label", stem)
        out = work / f"SHOPTALK_{label}.cube"
        vf = grade.chain(g, G["lut_root"])
        build_cube(vf, out, f"Shop Talk {label}")
        # verify: frame through the combined cube vs frame through the original chain
        src = cams[stem]["file"]
        diffs = [float(np.abs(grade.frame(src, t, f"lut3d=file='{out}':interp=tetrahedral")
                              - grade.frame(src, t, vf)).mean()) for t in (300.0, 900.0)]
        ok = max(diffs) < 3.0
        print(f"{out.name}: {out.stat().st_size // 1024} KB  diff vs chain {diffs[0]:.2f}/{diffs[1]:.2f} (0-255)  {'OK' if ok else 'CHECK'}")
        if not ok:
            raise SystemExit("combined LUT does not match its chain")
        made.append(out)
    if deliver_dir:
        d = Path(deliver_dir); d.mkdir(parents=True, exist_ok=True)
        for p in made:
            dst = d / p.name
            if dst.exists():
                if filecmp.cmp(p, dst, shallow=False): print(f"  same file already at {dst}"); continue
                raise SystemExit(f"{dst} exists and differs (never overwrite) - change the label")
            shutil.copy2(p, dst)
            assert filecmp.cmp(p, dst, shallow=False)
            print(f"  delivered {dst}")
    return made
