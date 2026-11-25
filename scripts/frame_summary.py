"""Local prep for visual checks: one-page summary + at most two images.

Claude reads summary.md first and opens sheet.jpg / flagged.jpg only when the text
is not enough, instead of reading every frame or a full-size contact sheet.

  .venv/bin/python scripts/frame_summary.py VIDEO_OR_DIR [--n 24] [--out DIR]

Per frame: time, luma, sharpness, faces (Apple Vision), on-screen text (Vision OCR).
Flags: dark, blown, soft, no-face, dup. Runs fully on the Mac.
"""
import argparse, collections, difflib, json, math, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nljbs import media  # noqa: E402  (puts static ffmpeg on PATH)

SWIFT = Path(__file__).with_name("vision_frames.swift")
IMG = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def extract(video, n, dst):
    dur = float(media.probe(video)["format"]["duration"])
    frames = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        p = dst / f"f{i:03d}.jpg"
        # Full resolution: at 640px Vision misreads small text ("@" -> "O", "TT" -> "IT").
        subprocess.run([media.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
                        "-frames:v", "1", "-q:v", "2", "-y", str(p)], check=True)
        frames.append((p, f"{int(t // 60)}:{t % 60:05.2f}"))
    return frames


def measure(path):
    g = np.asarray(Image.open(path).convert("L").resize((320, 180)), dtype=np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return g, float(g.mean()), float(lap.var())


def vision(paths):
    # Compile once; `swift file.swift` recompiles every run (minutes).
    exe = media.WORK_ROOT / "bin" / "vision_frames"
    if not exe.exists() or exe.stat().st_mtime < SWIFT.stat().st_mtime:
        exe.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(SWIFT), "-o", str(exe)], check=True)
    r = subprocess.run([str(exe), *map(str, paths)], capture_output=True, text=True)
    if r.returncode:
        print("Vision step failed, continuing without faces/text:", r.stderr[-300:], file=sys.stderr)
        return {}
    return {d["path"]: d for d in map(json.loads, r.stdout.splitlines())}


def vote_handles(lines):
    """Group OCR readings of the same handle across frames; majority vote per letter.

    Returns [(handle, agree, total)]. agree = readings that match the vote exactly.
    """
    groups = []
    for s in (l.strip() for l in lines):
        if "@" not in s and "_" not in s:
            continue
        for g in groups:
            if difflib.SequenceMatcher(None, g[0].upper(), s.upper()).ratio() >= 0.75:
                g.append(s)
                break
        else:
            groups.append([s])
    out = []
    for g in groups:
        if len(g) < 2:
            continue
        # IG handles have no spaces: OCR spaces are misread "_".
        # shortcut: a real "." read as a space comes out as "_"; the crop check catches it.
        g = [s.replace(" ", "_") for s in g]
        n = collections.Counter(map(len, g)).most_common(1)[0][0]
        same = [s for s in g if len(s) == n]
        at = any(s.startswith("@") for s in same)  # then char 0 is the "@" slot, often read as Q/O
        body = [s[1:] for s in same] if at else same
        voted = ("@" if at else "") + "".join(collections.Counter(c).most_common(1)[0][0] for c in zip(*body))
        agree = sum(s[1:] == voted[1:] if at else s == voted for s in g)
        out.append((voted, agree, len(g)))
    return sorted(out, key=lambda h: -h[2])


def selftest():
    reads = ["@MIKE_DALTON_TATTOO", "@MIKE_DALTON_TATTOO", "QMIKE DALTON_TATTOO",
             "OMIKE_DALTON_TAITOO", "@MIKE DALTON_TATTOO", "THAT'S SO DOPE", "@MIKE_DALTON_TATT"]
    assert vote_handles(reads) == [("@MIKE_DALTON_TATTOO", 4, 6)], vote_handles(reads)
    real = ["QMIKE DALTON_TATTOO"] * 7 + ["@MIKE_DALTON_TATTOO"] * 7 + ["@MIKE DALTON_TATTOO"]  # R85 reel 01
    assert vote_handles(real) == [("@MIKE_DALTON_TATTOO", 15, 15)], vote_handles(real)
    assert vote_handles(["@solo_handle"]) == []
    print("selftest ok")


def sheet(items, out, thumb, cols):
    rows = math.ceil(len(items) / cols)
    w = thumb
    h = round(thumb * 9 / 16)
    canvas = Image.new("RGB", (cols * w, rows * (h + 14)), "black")
    d = ImageDraw.Draw(canvas)
    for i, (p, label) in enumerate(items):
        im = Image.open(p).convert("RGB")
        im.thumbnail((w, h))
        x, y = (i % cols) * w, (i // cols) * (h + 14)
        canvas.paste(im, (x + (w - im.width) // 2, y))
        d.text((x + 3, y + h + 1), label, fill="yellow")
    canvas.save(out, quality=80)


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--n", type=int, default=24, help="frames to sample from a video")
    ap.add_argument("--out", help="output dir (default: <src>_summary next to the source)")
    ap.add_argument("--no-face-check", action="store_true", help="skip no-face flag (b-roll, screens)")
    a = ap.parse_args()
    src = Path(a.src).expanduser()
    out = Path(a.out).expanduser() if a.out else src.parent / f"{src.stem}_summary"
    out.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        frames = [(p, p.stem[:18]) for p in sorted(src.iterdir()) if p.suffix.lower() in IMG]
    else:
        fdir = out / "frames"
        fdir.mkdir(exist_ok=True)
        frames = extract(src, a.n, fdir)
    if not frames:
        sys.exit(f"no frames in {src}")

    vis = vision([p for p, _ in frames])
    rows, prev = [], None
    for p, label in frames:
        g, luma, sharp = measure(p)
        v = vis.get(str(p), {})
        rows.append(dict(label=label, path=p, luma=luma, sharp=sharp,
                         faces=v.get("faces", []), text=v.get("text", []),
                         dup=prev is not None and float(np.abs(g - prev).mean()) < 2.0))
        prev = g
    med = float(np.median([r["sharp"] for r in rows]))
    for r in rows:
        r["flags"] = [f for f, on in (("dark", r["luma"] < 40), ("blown", r["luma"] > 215),
                                      ("soft", r["sharp"] < 0.4 * med),
                                      ("no-face", bool(vis) and not a.no_face_check and not r["faces"]),
                                      ("dup", r["dup"])) if on]

    lines = [f"# {src.name}: {len(rows)} frames", "",
             f"Sharpness median {med:.0f}. Flagged {sum(bool(r['flags']) for r in rows)}.", "",
             "| frame | luma | sharp | faces (x,y,w,h) | text | flags |", "|---|---|---|---|---|---|"]
    for r in rows:
        faces = " ".join(f"({f[0]:.2f},{f[1]:.2f},{f[2]:.2f},{f[3]:.2f})" for f in r["faces"]) or "-"
        text = " / ".join(r["text"])[:80].replace("|", "/") or "-"
        lines.append(f"| {r['label']} | {r['luma']:.0f} | {r['sharp']:.0f} | {faces} | {text} | {' '.join(r['flags'])} |")
    handles = vote_handles([t for r in rows for t in r["text"]])
    if handles:
        lines += ["", "## Handles (OCR vote across frames; check one crop before anything public)"]
        lines += [f"- {h}  ({agree}/{n} frames agree)" for h, agree, n in handles]
    (out / "summary.md").write_text("\n".join(lines) + "\n")

    # Two images max: a small overview sheet, and larger thumbs of flagged frames only.
    sheet([(r["path"], r["label"]) for r in rows], out / "sheet.jpg", thumb=160, cols=8)
    flagged = [(r["path"], f"{r['label']} {','.join(r['flags'])}") for r in rows if r["flags"]][:12]
    if flagged:
        sheet(flagged, out / "flagged.jpg", thumb=320, cols=4)
    print(out / "summary.md")


if __name__ == "__main__":
    main()
