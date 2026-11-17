"""ffmpeg/ffprobe helpers. Reads from the drive, writes only to the local work dir."""
import json
import os
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import static_ffmpeg

static_ffmpeg.add_paths(weak=True)
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

WORK_ROOT = Path(os.environ.get("NLJBS_WORK", Path.home() / "nljbs-work"))
DRIVE = Path("/Volumes/NLJBS Drive")


def probe(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def summarize(path):
    """Flat summary of the first video and audio stream."""
    info = probe(path)
    fmt = info.get("format", {})
    s = {"file": Path(path).name, "path": str(path), "duration": float(fmt.get("duration", 0) or 0)}
    for st in info.get("streams", []):
        if st.get("codec_type") == "video" and "video" not in s:
            rate = Fraction(st.get("r_frame_rate", "0/1"))
            s["video"] = {
                "codec": st.get("codec_name"),
                "profile": st.get("profile"),
                "pix_fmt": st.get("pix_fmt"),
                "width": st.get("width"),
                "height": st.get("height"),
                "fps": float(rate) if rate else 0.0,
                "fps_str": st.get("r_frame_rate"),
                "color_range": st.get("color_range"),
                "color_primaries": st.get("color_primaries"),
                "color_transfer": st.get("color_transfer"),
                "color_space": st.get("color_space"),
            }
        if st.get("codec_type") == "audio" and "audio" not in s:
            s["audio"] = {
                "codec": st.get("codec_name"),
                "sample_rate": int(st.get("sample_rate", 0)),
                "channels": st.get("channels"),
                "bits": st.get("bits_per_raw_sample") or st.get("bits_per_sample"),
            }
    return s


def xml_rate(fps):
    """(timebase, ntsc) for xmeml, from a measured frame rate."""
    for tb in (24, 25, 30, 50, 60, 120):
        if abs(fps - tb * 1000 / 1001) < 0.01:
            return tb, True
        if abs(fps - tb) < 0.01:
            return tb, False
    raise ValueError(f"unexpected frame rate {fps}")


def extract_audio(src, cache_dir, sr=8000, channel=0, tag=None):
    """Mono float32 of one channel at `sr`, cached as .f32 in cache_dir. Runs in the foreground."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tag = tag or Path(src).stem
    out = cache_dir / f"{tag}_{sr}_c{channel}.f32"
    if not out.exists():
        tmp = cache_dir / (out.name + ".part")
        subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-i", str(src), "-map", "0:a:0",
             "-af", f"pan=mono|c0=c{channel}", "-ar", str(sr), "-f", "f32le", str(tmp)],
            check=True,
        )
        tmp.rename(out)
    return np.fromfile(out, dtype=np.float32)


def frame_at(src, t, out_jpg, width=480):
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
         "-vf", f"scale={width}:-2", str(out_jpg)],
        check=True,
    )
