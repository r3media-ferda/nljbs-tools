"""`nljbs probe <recording folder>`: inventory sources, flag oddities, draft episode.yaml."""
import datetime as dt
import re
import subprocess
from pathlib import Path

import yaml

from . import media

SHOPTALK = media.DRIVE / "WORKING SHOP TALM FILES"
OBS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}\.mp4$", re.I)
TAKE_RE = re.compile(r"^Mic (\d+) ?#(\d+)\.wav$", re.I)


def classify(name):
    up = name.upper()
    if name.startswith("._"):
        return None
    if OBS_RE.match(name):
        return "obs"
    if up.endswith(".MP4"):
        if up.startswith("AVE"):
            return "ave"
        if up.startswith("093A"):
            return "093a"
        if up.startswith("C0"):
            return "wide"
        return "video"
    if up.endswith(".WAV"):
        return "mic_export"
    if up.endswith(".BAND"):
        return "band"
    return None


def who_from_name(fname):
    """'mic 1-porter.wav' / 'MIC 2 - AC.wav' -> 'Porter' / 'AC'. TODO when the name carries no person."""
    m = re.match(r"^mic\s*\d+\s*-\s*(.+?)\.wav$", fname, re.I)
    if not m:
        return "TODO"
    w = m.group(1).strip()
    return w.upper() if len(w) <= 2 else w.title()


def last_release(exclude=None):
    """Highest release number on the drive, ignoring files inside `exclude` (the folder being probed)."""
    nums = []
    for p in SHOPTALK.rglob("*"):
        if p.name.startswith("._"):
            continue
        if exclude and Path(exclude) in p.parents:
            continue
        for m in re.finditer(r"(?:^|[_ ])R(\d{2,3})_|RELEASE (\d{2,3})\b", p.name, re.I):
            nums.append(int(m.group(1) or m.group(2)))
    return max(nums) if nums else None


def pick_band_takes(band, end_time):
    """Per mic, the raw take whose mtime is closest to when the cameras stopped."""
    files = Path(band) / "Media" / "Audio Files"
    takes = {}
    for f in files.iterdir():
        m = TAKE_RE.match(f.name)
        if not m or f.name.startswith("._"):
            continue
        mic = int(m.group(1))
        gap = abs(f.stat().st_mtime - end_time)
        if mic not in takes or gap < takes[mic][0]:
            takes[mic] = (gap, f)
    return {mic: f for mic, (gap, f) in sorted(takes.items()) if gap < 15 * 60}


def run(folder, work=None):
    folder = Path(folder)
    rec_slug = f"{folder.parent.name}_{folder.name.replace(' ', '')}"
    work = Path(work) if work else media.WORK_ROOT / rec_slug
    (work / "frames").mkdir(parents=True, exist_ok=True)

    found = {}
    for p in sorted(folder.iterdir()):
        kind = classify(p.name)
        if kind:
            found.setdefault(kind, []).append(p)

    flags, sources = [], {}
    videos = [p for k in ("ave", "093a", "wide", "obs", "video") for p in found.get(k, [])]
    for p in videos:
        s = media.summarize(p)
        s["kind"] = classify(p.name)
        sources[p.name] = s
        v = s.get("video", {})
        fps = v.get("fps", 0)
        if abs(fps - 29.97) > 0.01:
            flags.append(f"{p.name}: {v.get('fps_str')} fps ({fps:.3f}), Premiere conforms to 29.97")
        if not v.get("color_transfer") or v.get("color_transfer") == "unknown":
            flags.append(f"{p.name}: untagged color ({v.get('pix_fmt')}, range {v.get('color_range')})")
        if "audio" not in s:
            flags.append(f"{p.name}: NO AUDIO STREAM, cannot sync by audio")

    durs = {n: s["duration"] for n, s in sources.items() if s["kind"] != "obs"}
    if durs:
        longest = max(durs.values())
        for n, d in durs.items():
            if d < longest - 120:
                flags.append(f"{n}: {d/60:.1f} min vs longest {longest/60:.1f} min, stops early")

    # OBS runs on the Mac clock; camera clocks drift (11.23.26 Canons ran an hour ahead)
    clock = found.get("obs") or videos
    end_time = max(p.stat().st_mtime for p in clock) if clock else 0
    mics = {}
    exports = found.get("mic_export", [])
    if exports:
        mode = "garageband_export"
        for p in exports:
            s = media.summarize(p)
            mics[p.name] = s
            if s.get("audio", {}).get("channels") == 2:
                flags.append(f"{p.name}: stereo export, assumed dual-mono, using channel 1")
    else:
        mode = "raw_band"
        for band in found.get("band", []):
            for mic, f in pick_band_takes(band, end_time).items():
                s = media.summarize(f)
                mics[f.name] = s
        flags.append("No GarageBand mic exports in folder. Built on raw .band takes "
                     "(R80 rule: export from GarageBand and re-point before the edit).")
    mdurs = {round(s["duration"], 1) for s in mics.values()}
    if len(mdurs) > 1:
        flags.append(f"Mic files differ in length {sorted(mdurs)}: check takes")

    # contact sheet: one frame per camera, 10 min in
    tiles = []
    for n, s in sources.items():
        jpg = work / "frames" / f"{Path(n).stem}.jpg"
        media.frame_at(s["path"], min(600, s["duration"] / 2), jpg)
        tiles.append(jpg)
    sheet = work / "contact_sheet.jpg"
    if tiles:
        ins = sum((["-i", str(t)] for t in tiles), [])
        n = len(tiles)
        cols = 2
        layout = "|".join(f"{(i % cols) * 480}_{(i // cols) * 270}" for i in range(n))
        fc = "".join(f"[{i}]scale=480:270[s{i}];" for i in range(n)) + "".join(f"[s{i}]" for i in range(n))
        fc += f"xstack=inputs={n}:layout={layout}:fill=black" if n > 1 else "copy"
        subprocess.run([media.FFMPEG, "-v", "error", "-y", *ins, "-filter_complex", fc, str(sheet)], check=True)

    last = last_release(exclude=folder)
    rel = (last or 0) + 1
    rec_date = folder.parent.name  # MM.DD.YY
    episode = {
        "release": rel,
        "release_note": f"last release found on drive: R{last}; confirm",
        "recording_date": rec_date,
        "recording_folder": str(folder),
        "work_dir": str(work),
        "mic_mode": mode,
        "mics": [{"file": s["path"], "who": who_from_name(s["file"]), "handle": "TODO"} for s in mics.values()],
        "cameras": [
            {"file": s["path"], "kind": s["kind"], "who": "TODO"} for s in sources.values() if s["kind"] != "obs"
        ],
        "obs": [s["path"] for s in sources.values() if s["kind"] == "obs"],
        "guests": [],
        "probed": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (work / "episode.yaml").write_text(yaml.safe_dump(episode, sort_keys=False, allow_unicode=True))
    (work / "probe.yaml").write_text(yaml.safe_dump({"sources": sources, "mics": mics, "flags": flags},
                                                    sort_keys=False, allow_unicode=True))

    print(f"Recording: {folder}\nWork dir:  {work}\nRelease:   R{rel} (last on drive R{last})\n")
    print("Sources:")
    for n, s in {**sources, **mics}.items():
        v, a = s.get("video", {}), s.get("audio", {})
        vs = f"{v['codec']} {v['pix_fmt']} {v['fps']:.3f}fps {v.get('color_transfer')}" if v else ""
        as_ = f"{a.get('codec')} {a.get('sample_rate')}Hz {a.get('channels')}ch" if a else ""
        print(f"  {n:34s} {s['duration']/60:6.2f} min  {vs:42s} {as_}")
    print("\nFlags:")
    for f in flags:
        print("  !", f)
    print(f"\nContact sheet: {sheet}\nDraft config:  {work / 'episode.yaml'} (fill in who's on each mic/camera)")
    return episode
