"""`palefire transcribe <shoot folder> [stems...]`: Parakeet word timings for each camera clip.

Writes <work>/transcripts/<stem>.words.json  [{"w", "t0", "t1"}], seconds on the clip's own timeline
       <work>/transcripts/<stem>.txt         "   12.3  text", one line per run of speech (new line after 1 s quiet)
These are the files `palefire cut` reads. Existing transcripts are kept unless --force.
Reads the drive, writes only to the work dir. One clip at a time in the foreground.
"""
import json
import re
from pathlib import Path

from nljbs import media
from nljbs.transcribe import SR, asr

from .probe import WORK_ROOT

VIDEO = {".mp4", ".mov", ".mxf"}


def work_dir(folder, work=None):
    """Same default as `palefire probe`: ~/r3-work/palefire/<parent>_<folder> in lower snake case."""
    folder = Path(folder)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{folder.parent.name}_{folder.name}").strip("_").lower()
    return Path(work).expanduser() if work else WORK_ROOT / slug


def clips(folder):
    raw = Path(folder) / "RAW VIDEO"
    root = raw if raw.is_dir() else Path(folder)
    return sorted(p for p in root.iterdir() if p.suffix.lower() in VIDEO and not p.name.startswith("."))


def lines(words, gap=1.0):
    out, cur = [], []
    for w in words:
        if cur and w["t0"] - cur[-1]["t1"] > gap:
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return "\n".join(f"{ln[0]['t0']:8.1f}  " + " ".join(w["w"] for w in ln) for ln in out) + "\n"


def run(folder, work=None, stems=None, force=False):
    work = work_dir(folder, work)
    out = work / "transcripts"
    out.mkdir(parents=True, exist_ok=True)
    todo = [p for p in clips(folder) if not stems or p.stem in stems]
    if stems and len(todo) < len(stems):
        missing = set(stems) - {p.stem for p in todo}
        raise SystemExit(f"not found in {folder}: {', '.join(sorted(missing))}")
    for p in todo:
        dst = out / f"{p.stem}.words.json"
        if dst.exists() and not force:
            print(f"{p.stem}: kept existing transcript (--force to redo)")
            continue
        x = media.extract_audio(p, work / "audio", sr=SR)
        words = asr(x)
        dst.write_text(json.dumps(words))
        (out / f"{p.stem}.txt").write_text(lines(words))
        print(f"{p.stem}: {len(words)} words, {len(x) / SR:.0f} s -> {dst}")
