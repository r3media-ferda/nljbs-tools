"""Social delivery for finished reels: a platform-safe export, and a short-lived public link for Rella to fetch.

`palefire social <plan> [ids]`  -> <id>_SOCIAL.mp4 next to <id>_FINAL.mp4, checked against SPEC.
`palefire serve <file>...`      -> public https links for Rella's attach_rella_media_to_content, then shuts down.

Specs (Meta developer docs, checked 2026-11-20):
  Instagram Reels (IG User Media): H.264/HEVC, progressive, closed GOP, 4:2:0, 23-60 fps, video VBR <= 25 Mbps,
    AAC 48 kHz mono/stereo at 128 kbps, MP4 with no edit lists and moov at the front, 3 s to 15 min, <= 300 MB.
  Facebook Reels (Reels Publishing API): 3 to 90 s, 24-60 fps, 1080x1920 recommended (540x960 min), H.264, AAC 48 kHz.
We encode to the overlap: H.264 High, 29.97 fps, video capped at 12 Mbps (half Instagram's limit, plenty for 1080p),
AAC 128 kbps 48 kHz stereo, 3-90 s. A 60 s reel lands near 90 MB, well under every cap.
Loudness: -14 LUFS integrated, true peak <= -1 dBTP (the house standard; see docs/OZ_EDITING_WORKFLOW.md, Audio).
Platforms turn loud uploads down and never turn quiet ones up, so every export is measured, brought to -14 LUFS with
gain + a peak limiter (re-measured after the AAC encode until it lands), and checked again in check().

`palefire social <file.mp4>...` takes finished exports straight from Premiere too: <stem>_SOCIAL.mp4 goes in --out
(default ~/r3-work/social), never next to the source on a client drive.

Serving: Rella imports media only from a public https URL. `serve` copies the named files into a fresh folder,
serves that folder alone on a free localhost port (bound in-process, so no other program can be behind the port),
checks each file locally, opens a Cloudflare quick tunnel (no account), checks each file through the tunnel, prints
the URLs, and closes everything on Ctrl-C, SIGTERM, or after --minutes (default 10). Nothing else on the Mac is exposed.
"""
import functools
import http.server
import json
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote

import yaml

from nljbs import media

SPEC = dict(width=1080, height=1920, fps=(23.0, 60.0), vbr_max=12_000_000, dur=(3.0, 90.0),
            size_max=300 * 1024 * 1024, lufs=-14.0, lufs_tol=1.0, tp_max=-1.0)
TP_AIM = -1.5  # loudnorm's analysis-pass target; only its input_* measurements are used
SOCIAL_OUT = Path("~/r3-work/social").expanduser()
CLOUDFLARED = Path("~/r3-work/bin/cloudflared").expanduser()


# ---------- export ----------

def loudness(path):
    """EBU R128 measure of a file's audio: dict(I, TP, LRA, thresh, offset) from ffmpeg loudnorm's analysis pass."""
    r = subprocess.run([media.FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-vn",
                        "-af", f"loudnorm=I={SPEC['lufs']}:TP={TP_AIM}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    return dict(I=float(m["input_i"]), TP=float(m["input_tp"]), LRA=float(m["input_lra"]),
                thresh=float(m["input_thresh"]), offset=float(m["target_offset"]))


def export(src, dst):
    """Re-encode src to SPEC at -14 LUFS / <= -1 dBTP; returns the source loudness measured before.

    The video is encoded once; the audio is then re-muxed onto it with gain + a fixed peak limiter, measured after
    the AAC encode (which overshoots the limiter by a dB or so), and redone with corrected gain until it lands.
    Same approach as nljbs reels: the limiter only tightens when the peaks miss, gain alone chases the loudness."""
    src, dst = Path(src), Path(dst)
    before = loudness(src)
    video = dst.with_name(dst.stem + ".video.mp4")
    subprocess.run([media.FFMPEG, "-v", "error", "-y", "-i", str(src), "-an",
                    "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-preset", "slow",
                    "-crf", "18", "-maxrate", "12M", "-bufsize", "24M", "-flags", "+cgop", "-g", "60",
                    "-r", "30000/1001",
                    # Canon MP4s are full range (yuvj420p, pc) and the renders keep it; platforms expect limited (tv)
                    # BT.709, so convert the levels and tag them rather than trust players to read the range flag
                    "-vf", f"scale={SPEC['width']}:{SPEC['height']}:in_range=auto:out_range=tv,format=yuv420p",
                    "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709",
                    "-color_primaries", "bt709", "-color_trc", "bt709", str(video)], check=True)
    gain = SPEC["lufs"] - before["I"]
    try:
        for lim in (0.80, 0.72, 0.64, 0.56):  # sample-peak ceiling: -1.9, -2.9, -3.9, -5.0 dBFS
            for _ in range(4):
                subprocess.run([media.FFMPEG, "-v", "error", "-y", "-i", str(video), "-i", str(src),
                                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                                "-af", f"volume={gain:.2f}dB,alimiter=limit={lim:.3f}:level=false:attack=2:release=40,"
                                       "aresample=48000",
                                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-shortest",
                                "-movflags", "+faststart", "-use_editlist", "0", str(dst)], check=True)
                got = loudness(dst)
                if abs(got["I"] - SPEC["lufs"]) <= 0.3:
                    break
                gain += SPEC["lufs"] - got["I"]
            if got["TP"] <= SPEC["tp_max"] - 0.1:
                break
    finally:
        video.unlink(missing_ok=True)
    return before


def check(path):
    """([problems], stats) for a file against SPEC; no problems means it is safe for Instagram and Facebook Reels."""
    out = subprocess.run([media.FFPROBE, "-v", "error", "-show_entries",
                          "format=duration,size:stream=codec_type,codec_name,width,height,pix_fmt,color_range,r_frame_rate,"
                          "bit_rate,sample_rate,channels", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True)
    info = json.loads(out.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur, size = float(info["format"]["duration"]), int(info["format"]["size"])
    n, d = map(int, v["r_frame_rate"].split("/"))
    fps = n / d
    bad = []
    if v["codec_name"] != "h264" or v["pix_fmt"] != "yuv420p" or v.get("color_range") not in ("tv", None):
        bad.append(f"video {v['codec_name']} {v['pix_fmt']} {v.get('color_range')} (want h264 yuv420p tv)")
    if (int(v["width"]), int(v["height"])) != (SPEC["width"], SPEC["height"]):
        bad.append(f"size {v['width']}x{v['height']} (want 1080x1920)")
    if not SPEC["fps"][0] <= fps <= SPEC["fps"][1]:
        bad.append(f"{fps:.2f} fps")
    if int(v.get("bit_rate", 0)) > SPEC["vbr_max"] * 1.05:
        bad.append(f"video {int(v['bit_rate']) / 1e6:.1f} Mbps (cap 12)")
    if a is None:
        bad.append("no audio")
    elif a["codec_name"] != "aac" or int(a["sample_rate"]) != 48000 or int(a.get("bit_rate", 0)) > 135_000:
        bad.append(f"audio {a['codec_name']} {a['sample_rate']} Hz {int(a.get('bit_rate', 0)) // 1000} kbps")
    if not SPEC["dur"][0] <= dur <= SPEC["dur"][1]:
        bad.append(f"{dur:.1f} s (Facebook Reels take 3-90 s)")
    if size > SPEC["size_max"]:
        bad.append(f"{size / 1e6:.0f} MB (Instagram cap 300 MB)")
    with open(path, "rb") as f:  # moov before mdat: plays before it finishes downloading
        head = f.read(64 * 1024)
    if head.find(b"moov") < 0 or (0 <= head.find(b"mdat") < head.find(b"moov")):
        bad.append("moov atom not at the front")
    lu = loudness(path) if a is not None else None
    if lu and abs(lu["I"] - SPEC["lufs"]) > SPEC["lufs_tol"]:
        bad.append(f"loudness {lu['I']:.1f} LUFS (want {SPEC['lufs']:.0f} ±{SPEC['lufs_tol']:.0f})")
    if lu and lu["TP"] > SPEC["tp_max"]:
        bad.append(f"true peak {lu['TP']:+.1f} dBTP (cap {SPEC['tp_max']:.0f})")
    return bad, dict(dur=dur, mb=size / 1e6, vmbps=int(v.get("bit_rate", 0)) / 1e6,
                     lufs=lu["I"] if lu else None, tp=lu["TP"] if lu else None)


def _report(src, dst):
    """Export one file, check it, print a line; True when it passes."""
    before = export(src, dst)
    bad, st = check(dst)
    print(f"{dst.name}: {st['dur']:.1f} s, {st['mb']:.0f} MB, video {st['vmbps']:.1f} Mbps, "
          f"audio {before['I']:.1f} -> {st['lufs']:.1f} LUFS, peak {st['tp']:+.1f} dBTP  "
          + ("OK for Instagram + Facebook Reels" if not bad else "PROBLEMS: " + "; ".join(bad)))
    return not bad


def run_files(files, out=None):
    """Premiere exports (or any finished MP4s) -> <out>/<stem>_SOCIAL.mp4."""
    out = Path(out).expanduser() if out else SOCIAL_OUT
    out.mkdir(parents=True, exist_ok=True)
    fails = 0
    for f in map(Path, files):
        if not f.is_file():
            raise SystemExit(f"{f}: not a file")
        dst = out / f"{f.stem}_SOCIAL.mp4"
        if dst.resolve() == f.resolve():
            raise SystemExit(f"{f}: output would overwrite the source")
        fails += not _report(f, dst)
    if fails:
        raise SystemExit(f"{fails} file(s) fail the social spec")


def run_social(plan_yaml, ids=None):
    cfg = yaml.safe_load(Path(plan_yaml).read_text())
    cuts = Path(cfg["work"]).expanduser() / "cuts"
    fails = 0
    for reel in cfg["reels"]:
        if ids and reel["id"] not in ids:
            continue
        src = cuts / f"{reel['id']}_FINAL.mp4"
        if not src.exists():
            print(f"{reel['id']}: no {src.name}, skipped")
            continue
        fails += not _report(src, cuts / f"{reel['id']}_SOCIAL.mp4")
    if fails:
        raise SystemExit(f"{fails} file(s) fail the social spec")


# ---------- serve ----------

class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("  fetch: " + (fmt % args) + "\n")


_last = {}


def _head_ok(url, size, timeout=20, doh=False):
    """HEAD via the system curl: the python.org Python here has no CA bundle unless Install Certificates was run.
    doh=True resolves through Cloudflare DNS-over-HTTPS: a brand-new tunnel hostname looked up too early gets a
    'not found' that macOS then caches, so public checks skip the system resolver."""
    cmd = ["curl", "-sSI", "--max-time", str(timeout)] + (["--doh-url", "https://1.1.1.1/dns-query"] if doh else [])
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    _last.update(url=url, rc=r.returncode, out=r.stdout.strip()[:400], err=r.stderr.strip()[:200])
    if r.returncode != 0:
        return False
    head = r.stdout.lower()
    status = head.split("\n", 1)[0].split()
    return (len(status) > 1 and status[1] == "200" and f"content-length: {size}" in head
            and "content-type: video/" in head)


def serve(files, minutes=10):
    if not CLOUDFLARED.exists():
        raise SystemExit(f"{CLOUDFLARED} missing: get cloudflared-darwin-arm64.tgz from Cloudflare's GitHub releases")
    files = [Path(f).expanduser().resolve() for f in files]
    for f in files:
        if not f.is_file():
            raise SystemExit(f"{f}: not a file")
        bad, _ = check(f)
        if bad:
            raise SystemExit(f"{f.name} fails the social spec ({'; '.join(bad)}); run `palefire social` first")
    root = Path(tempfile.mkdtemp(prefix="palefire_serve_"))
    for f in files:
        shutil.copy2(f, root / f.name)

    # port 0: the OS hands us a free port and this process holds it, so the tunnel can only reach this folder
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Handler, directory=str(root)))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    for f in files:
        if not _head_ok(f"http://127.0.0.1:{port}/{quote(f.name)}", f.stat().st_size, timeout=5):
            httpd.shutdown()
            shutil.rmtree(root, ignore_errors=True)
            raise SystemExit(f"local check failed for {f.name}; no tunnel opened")

    log = Path(f"{root}.tunnel.log")
    tun = subprocess.Popen([str(CLOUDFLARED), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                           stdout=open(log, "w"), stderr=subprocess.STDOUT)

    def close(*_):
        tun.terminate()
        try:
            tun.wait(5)
        except subprocess.TimeoutExpired:
            tun.kill()
        httpd.shutdown()
        shutil.rmtree(root, ignore_errors=True)
        print("CLOSED", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, close)
    signal.signal(signal.SIGINT, close)
    base = None
    for _ in range(40):
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", log.read_text())
        if m:
            base = m.group(0)
            break
        time.sleep(1)
    if not base:
        print("tunnel did not come up", flush=True)
        close()
    time.sleep(6)  # let the new hostname reach DNS before anyone asks for it
    for f in files:
        url = f"{base}/{quote(f.name)}"  # spaces in Premiere export names -> %20
        for _ in range(20):
            if _head_ok(url, f.stat().st_size, doh=True):
                break
            time.sleep(2)
        else:
            print(f"public check failed for {f.name}: {_last}", flush=True)
            close()
        print(f"URL {f.name} {url}", flush=True)
    print(f"READY: closes in {minutes} min, or on Ctrl-C / SIGTERM", flush=True)
    time.sleep(minutes * 60)
    close()
