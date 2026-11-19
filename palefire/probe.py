"""`palefire probe <shoot folder>`: inventory a Pale Fire shoot, flag oddities, draft shoot.yaml.

Reads from the drive only. Everything it writes goes to ~/r3-work/palefire/<slug>/ (override with R3_WORK).
"""
import datetime as dt
import os
import re
import subprocess
from fractions import Fraction
from pathlib import Path

import yaml

from nljbs import media

WORK_ROOT = Path(os.environ.get("R3_WORK", Path.home() / "r3-work")) / "palefire"
LUT_DIR = media.DRIVE / "canon-lut-202510"

VIDEO_EXT = {".mp4", ".mov", ".mxf"}
RAW_EXT = {".cr3", ".cr2", ".arw", ".nef", ".dng"}
STILL_EXT = {".jpg", ".jpeg", ".heic", ".png", ".tif", ".tiff"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aif", ".aiff"}
# Canon and iPhone both count with the last 4 digits (AVE1 9815, 093A 7629, IMG_ 2197); 9999 wraps to 0001.
NUM_RE = re.compile(r"^(.+?)(\d{4})(?:-\d+)?$", re.I)

TARGET_FPS = 30000 / 1001
SCENE_GAP_MIN = 10  # clips further apart than this start a new scene
FONT = "/System/Library/Fonts/Helvetica.ttc"  # explicit font: the static ffmpeg has no fontconfig


def kind_of(p):
    ext = p.suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in RAW_EXT:
        return "raw"
    if ext in STILL_EXT:
        return "still"
    if ext in AUDIO_EXT:
        return "audio"
    return None


def camera_of(name, fmt_tags):
    model = fmt_tags.get("com.apple.quicktime.model") or fmt_tags.get("model") or ""
    up = name.upper()
    if model.startswith("iPhone") or up.startswith("IMG_"):
        return "iphone", model or "iPhone"
    if up.startswith("AVE"):
        return "canon", "Canon (AVE prefix)"
    if up.startswith("093A") or "CAEP" in fmt_tags.get("compatible_brands", ""):
        return "canon", "Canon (default prefix)"
    if up.startswith("DJI"):
        return "drone", "DJI"
    return "other", model or "unknown"


def luma_stats(path, t, bits):
    """YMIN/YAVG/YMAX of one frame, scaled 0-1. Log footage sits in a narrow band in the middle."""
    r = subprocess.run(
        [media.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
         "-vf", "signalstats,metadata=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    vals = dict(re.findall(r"lavfi\.signalstats\.(YMIN|YLOW|YAVG|YHIGH|YMAX)=([\d.]+)", r.stdout))
    full = (1 << bits) - 1
    return {k.lower(): round(float(v) / full, 3) for k, v in vals.items()} if vals else {}


def video_info(p):
    info = media.probe(p)
    fmt = info.get("format", {})
    tags = fmt.get("tags", {})
    v = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
    a = next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)
    tc = next((s.get("tags", {}).get("timecode") for s in info["streams"] if s.get("codec_tag_string") == "tmcd"),
              tags.get("timecode"))
    r_fps = float(Fraction(v.get("r_frame_rate", "0/1")) or 0)
    avg = Fraction(v.get("avg_frame_rate", "0/1"))
    avg_fps = float(avg) if avg else r_fps
    rot = next((sd.get("rotation") for sd in v.get("side_data_list", []) if "rotation" in sd), 0) or 0
    w, h = v.get("width", 0), v.get("height", 0)
    if abs(int(rot)) % 180 == 90:
        w, h = h, w
    pix = v.get("pix_fmt", "")
    bits = 12 if "12" in pix else 10 if "10" in pix else 8
    created = tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time")
    cam, model = camera_of(p.name, tags)
    dur = float(fmt.get("duration", 0) or 0)
    return {
        "file": p.name,
        "path": str(p),
        "camera": cam,
        "model": model,
        "duration": round(dur, 2),
        "created": local_time(created),
        "timecode": tc,
        "codec": v.get("codec_name"),
        "pix_fmt": pix,
        "bits": bits,
        "fps": round(r_fps, 3),
        "fps_avg": round(avg_fps, 3),
        "vfr": abs(avg_fps - r_fps) > 0.05,
        "rotation": int(rot),
        "display": f"{w}x{h}",
        "orientation": "vertical" if h > w else "horizontal",
        "transfer": v.get("color_transfer") or "untagged",
        "audio": f"{a.get('codec_name')} {a.get('channels')}ch {a.get('sample_rate')}Hz" if a else None,
        "luma": luma_stats(p, dur / 2, bits),
    }


def local_time(s):
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s
    return t.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def is_log(c):
    """Guess: 10-bit+, no transfer tag, and blacks lifted well above legal black (64/1023 = 0.063).

    YMAX is useless here: a practical light in frame clips it to 1.0 even in log.
    """
    lifted = c["luma"].get("ymin", 0) > 0.09 if c["luma"] else True
    return c["bits"] >= 10 and c["transfer"] in ("untagged", "unknown") and lifted


def number_gaps(names):
    """Per filename prefix, the camera counter numbers missing between the lowest and highest file."""
    seen = {}
    for n in names:
        m = NUM_RE.match(Path(n).stem)
        if m:
            seen.setdefault(m.group(1).upper(), set()).add(int(m.group(2)))
    gaps = {}
    for pre, nums in seen.items():
        if min(nums) < 1000 and max(nums) > 9000:  # counter wrapped 9999 -> 0001 mid-shoot
            nums = {n + 9999 if n < 5000 else n for n in nums}
        lo, hi = min(nums), max(nums)
        missing = sorted(set(range(lo, hi + 1)) - nums)
        if missing:
            gaps[pre] = [r for r in ranges([n - 9999 if n > 9999 else n for n in missing])]
    return gaps


def ranges(nums):
    out, start = [], nums[0]
    for a, b in zip(nums, nums[1:] + [None]):
        if b != a + 1:
            out.append(f"{start}" if start == a else f"{start}-{a}")
            if b is not None:
                start = b
    return out


def fix_clocks(clips, flags):
    """Correct a camera whose clock disagrees with its own file times (Canon with DST off, say).

    For each camera, offset = file mtime - (created + duration). The file mtime is the Mac's reading of
    when the clip closed. If a camera's median offset is more than 5 minutes, shift its `created` by it
    so scenes from two cameras interleave correctly. The iPhone writes a time-zoned creationdate, so it
    normally reads close to 0.
    """
    by_cam = {}
    for c in clips:
        if c["created"]:
            t = dt.datetime.strptime(c["created"], "%Y-%m-%d %H:%M:%S")
            end = t + dt.timedelta(seconds=c["duration"])
            by_cam.setdefault(c["camera"], []).append(c["mtime"] - end.timestamp())
    for cam, offs in by_cam.items():
        offs.sort()
        med = offs[len(offs) // 2]
        if abs(med) < 300:
            continue
        mins = round(med / 60)
        flags.append(f"{cam} clock is {-mins:+d} min off its file times (DST or time zone set wrong?). "
                     f"Shifted its clip times by {mins:+d} min for scene grouping.")
        for c in clips:
            if c["camera"] == cam and c["created"]:
                t = dt.datetime.strptime(c["created"], "%Y-%m-%d %H:%M:%S") + dt.timedelta(minutes=mins)
                c["created_camera"] = c["created"]
                c["created"] = t.strftime("%Y-%m-%d %H:%M:%S")


def scenes(clips):
    timed = sorted((c for c in clips if c["created"]), key=lambda c: c["created"])
    out, cur, last = [], [], None
    for c in timed:
        t = dt.datetime.strptime(c["created"], "%Y-%m-%d %H:%M:%S")
        if last and (t - last).total_seconds() > SCENE_GAP_MIN * 60:
            out.append(cur)
            cur = []
        cur.append(c)
        last = t + dt.timedelta(seconds=c["duration"])
    if cur:
        out.append(cur)
    return out


def contact_sheet(clips, work, cols=6):
    frames = work / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for old in frames.glob("*.jpg"):
        old.unlink()
    vertical = sum(c["orientation"] == "vertical" for c in clips) >= len(clips) / 2
    tw, th = (270, 480) if vertical else (480, 270)
    i = 0
    for c in clips:
        for frac in (0.1, 0.5, 0.9):
            i += 1
            label = f"{Path(c['file']).stem}  {frac * c['duration']:.0f}s"
            subprocess.run(
                [media.FFMPEG, "-v", "error", "-y", "-ss", f"{c['duration'] * frac:.3f}", "-i", c["path"],
                 "-frames:v", "1", "-vf",
                 f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,"
                 f"drawtext=fontfile={FONT}:text='{label}':x=6:y=6:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.5",
                 str(frames / f"{i:04d}.jpg")],
                check=True,
            )
    rows = -(-i // cols)
    sheet = work / "contact_sheet.jpg"
    subprocess.run(
        [media.FFMPEG, "-v", "error", "-y", "-i", str(frames / "%04d.jpg"),
         "-vf", f"tile={cols}x{rows}:padding=4:color=black", "-frames:v", "1", "-q:v", "3", str(sheet)],
        check=True,
    )
    return sheet


def run(folder, work=None, sheet=True):
    folder = Path(folder)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{folder.parent.name}_{folder.name}").strip("_").lower()
    work = Path(work) if work else WORK_ROOT / slug
    work.mkdir(parents=True, exist_ok=True)

    files = {"video": [], "raw": [], "still": [], "audio": []}
    for p in sorted(folder.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            k = kind_of(p)
            if k:
                files[k].append(p)

    # Same clip copied into two subfolders (e.g. RAW/ and VIDEOS/): probe once, keep every location.
    uniq = {}
    for p in files["video"]:
        uniq.setdefault((p.name, p.stat().st_size), []).append(p)
    clips = []
    for (_, _), paths in uniq.items():
        c = video_info(paths[0])
        c["copies"] = [str(p) for p in paths[1:]]
        c["mtime"] = paths[0].stat().st_mtime
        clips.append(c)
    flags = []
    dupes = [c["file"] for c in clips if c["copies"]]
    if dupes:
        flags.append(f"{len(dupes)} clip(s) exist in two folders (same name and size), counted once: {', '.join(dupes[:6])}"
                     f"{' ...' if len(dupes) > 6 else ''}")

    fix_clocks(clips, flags)

    off_rate = {}
    for c in clips:
        if abs(c["fps"] - TARGET_FPS) > 0.01:
            off_rate.setdefault((c["camera"], c["fps"]), []).append(c["file"])
    for (cam, fps), names in off_rate.items():
        flags.append(f"{len(names)} {cam} clip(s) at {fps} fps, not 29.97. Premiere will conform them.")
    for c in clips:
        if c["vfr"]:
            flags.append(f"{c['file']}: variable frame rate (avg {c['fps_avg']}), transcode to CFR 29.97 before cutting")
        if c["rotation"]:
            c["note_rotation"] = True
        if not c["audio"]:
            flags.append(f"{c['file']}: no audio stream")
        c["log"] = is_log(c)

    rotated = [c["file"] for c in clips if c["rotation"]]
    if rotated:
        flags.append(f"{len(rotated)} clip(s) carry a rotation tag (shot vertical). XML builds must use display size, not coded size.")
    logs = [c["file"] for c in clips if c["log"]]
    if logs:
        cubes = sorted(p.name for p in LUT_DIR.glob("*.cube") if not p.name.startswith("._")) if LUT_DIR.exists() else []
        where = f"LUTs on NLJBS Drive: {', '.join(cubes[:4])}" if cubes else "NLJBS Drive not mounted, LUT folder not checked"
        flags.append(f"{len(logs)} clip(s) look like Canon Log (10-bit, untagged, flat). Needs a LUT. {where}")
    cams = sorted({c["model"] for c in clips})
    if len(cams) > 1:
        flags.append(f"Mixed cameras: {', '.join(cams)}. Match color before cutting together.")
    fps_set = sorted({c["fps"] for c in clips})
    if len(fps_set) > 1:
        flags.append(f"Mixed frame rates {fps_set}. Build the sequence at 29.97 (timebase 30, ntsc TRUE).")
    if clips and not files["audio"]:
        flags.append("No separate audio files. Camera audio only; if a lav recorded on its own, it is not in this folder.")
    gaps = number_gaps([p.name for k in ("video", "raw", "still") for p in files[k]])
    for pre, rs in gaps.items():
        flags.append(f"{pre}#### counter gaps {', '.join(rs)}: deleted takes, or files still on the card?")

    sc = scenes(clips)
    orient = "vertical" if sum(c["orientation"] == "vertical" for c in clips) >= len(clips) / 2 else "horizontal"
    total = sum(c["duration"] for c in clips)
    first = min((c["created"] for c in clips if c["created"]), default=None)

    shoot = {
        "client": "Pale Fire Brewing",
        "shoot": folder.name,
        "date": first[:10] if first else None,
        "folder": str(folder),
        "work_dir": str(work),
        "sequence": {"width": 1080 if orient == "vertical" else 1920,
                     "height": 1920 if orient == "vertical" else 1080,
                     "timebase": 30, "ntsc": True},
        "lut": "TODO" if logs else None,
        "music": "TODO (copy the track into the client folder, not an outside volume)",
        "scenes": [
            {"name": "TODO", "start": s[0]["created"][11:16], "clips": [c["file"] for c in s]} for s in sc
        ],
        "clips": [
            {"file": c["file"], "camera": c["camera"], "seconds": c["duration"], "log": c["log"],
             "who": "TODO", "notes": ""} for c in clips
        ],
        "stills": len(files["raw"]) + len(files["still"]),
        "probed": dt.datetime.now().isoformat(timespec="seconds"),
    }
    probe = {"clips": clips, "stills": {"raw": len(files["raw"]), "processed": len(files["still"])},
             "audio": [str(p) for p in files["audio"]], "counter_gaps": gaps, "flags": flags}

    shoot_yaml = work / "shoot.yaml"
    if shoot_yaml.exists():
        shoot_yaml = work / "shoot.new.yaml"  # never clobber notes Avery already filled in
    shoot_yaml.write_text(yaml.safe_dump(shoot, sort_keys=False, allow_unicode=True))
    (work / "probe.yaml").write_text(yaml.safe_dump(probe, sort_keys=False, allow_unicode=True))
    sheet_path = contact_sheet(clips, work) if (sheet and clips) else None

    print(f"Shoot:    {folder}\nWork dir: {work}")
    print(f"Clips:    {len(clips)} ({total / 60:.1f} min), stills {shoot['stills']}, audio files {len(files['audio'])}")
    print(f"Sequence: {shoot['sequence']['width']}x{shoot['sequence']['height']} 29.97\n")
    print(f"  {'file':16s} {'cam':7s} {'start':8s} {'sec':>6s}  {'video':34s} {'luma min/avg/p90':18s} audio")
    for c in clips:
        vid = f"{c['codec']} {c['bits']}bit {c['fps']} {c['display']}{' VFR' if c['vfr'] else ''}"
        lu = c["luma"]
        ls = f"{lu.get('ymin', 0):.2f}/{lu.get('yavg', 0):.2f}/{lu.get('yhigh', 0):.2f}" if lu else "-"
        log = " LOG" if c["log"] else ""
        start = c["created"][11:19] if c["created"] else "-"
        print(f"  {c['file']:16s} {c['camera']:7s} {start:8s} {c['duration']:6.1f}  {vid:34s} {ls:18s} {c['audio']}{log}")
    print("\nScenes (by clock time):")
    for i, s in enumerate(sc, 1):
        dur = sum(c["duration"] for c in s)
        print(f"  {i}. {s[0]['created'][11:16]}  {len(s)} clips, {dur / 60:.1f} min: {', '.join(Path(c['file']).stem for c in s)}")
    print("\nFlags:")
    for f in flags:
        print("  !", f)
    if sheet_path:
        print(f"\nContact sheet: {sheet_path}")
    print(f"Draft config:  {shoot_yaml} (name the scenes, fill in who, pick the LUT)")
    return shoot
