"""`nljbs sync <episode.yaml>`: speech-envelope multicam sync -> FCP7 xmeml _SYNCED.xml.

Method (handoff section 4): 8 kHz mono, band-limited speech-energy envelope, log-compressed,
coarse FFT xcorr at 10 ms, fine at 1 ms, drift windows at 0.5 ms, one constant offset per
source, placed on whole 29.97 frames, then re-measured from the written XML.

Offset o (seconds) = where the source's t=0 sits on the mic timeline. Negative = rolled first.
"""
import filecmp
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

import numpy as np
import yaml
from scipy import signal

from . import media

SR = 8000
FPS = 30000 / 1001
_SOS = signal.butter(4, [150, 3500], btype="band", fs=SR, output="sos")


# ---------- envelopes and matching ----------

def envelope(x, hop, win):
    """Log speech-energy envelope, one value per `hop` samples, mean removed."""
    y = signal.sosfiltfilt(_SOS, x.astype(np.float64))
    c = np.concatenate([[0.0], np.cumsum(y * y)])
    starts = np.arange(0, len(y) - win, hop)
    e = (c[starts + win] - c[starts]) / win
    e = np.log10(e + 1e-10)
    floor = np.percentile(e, 20)          # flatten silence so room noise doesn't vote
    e = np.maximum(e, floor)
    return (e - e.mean()).astype(np.float32)


def coarse_lag(r, c):
    """Lag L (in hops) with r[n] ~ c[n-L] over the full length, plus confidence."""
    xc = signal.correlate(r, c, mode="full", method="fft")
    lags = signal.correlation_lags(len(r), len(c), mode="full")
    i = int(np.argmax(xc))
    return int(lags[i]), float(xc[i] / (np.median(np.abs(xc)) + 1e-12))


def local_lag(r, c, center, radius, lo=None, hi=None):
    """Search lags center±radius (hops) using ref samples [lo, hi). Returns (lag, conf)."""
    lo = 0 if lo is None else max(0, lo)
    hi = len(r) if hi is None else min(len(r), hi)
    lags = np.arange(center - radius, center + radius + 1)
    # keep ref indices where c[n-L] exists for every lag searched
    lo = max(lo, int(lags.max()))
    hi = min(hi, len(c) + int(lags.min()))
    if hi - lo < 100:
        return None, 0.0
    rr = r[lo:hi]
    scores = np.array([np.dot(rr, c[lo - L:hi - L]) for L in lags]) / (hi - lo)
    i = int(np.argmax(scores))
    # confidence = Pearson correlation of the two envelopes at the best lag (0..1)
    cc = c[lo - lags[i]:hi - lags[i]]
    ra, ca = rr - rr.mean(), cc - cc.mean()
    conf = float(np.dot(ra, ca) / (np.linalg.norm(ra) * np.linalg.norm(ca) + 1e-12))
    # parabolic sub-hop refinement
    lag = float(lags[i])
    if 0 < i < len(scores) - 1:
        a, b, d = (float(v) for v in scores[i - 1:i + 2])
        den = a - 2 * b + d
        if den != 0:
            lag += 0.5 * (a - d) / den
    return lag, conf


def measure(ref, cam, expect=None):
    """Full method for one source. Returns dict with offset (s) and diagnostics."""
    out = {}
    if expect is None:
        r10, c10 = envelope(ref, 80, 160), envelope(cam, 80, 160)
        L, conf = coarse_lag(r10, c10)
        out["coarse_s"], out["coarse_conf"] = L * 0.010, round(conf, 1)
        expect = L * 0.010
    r1, c1 = envelope(ref, 8, 80), envelope(cam, 8, 80)
    L, conf = local_lag(r1, c1, round(expect / 0.001), 50)
    if L is None:
        raise RuntimeError("sources barely overlap")
    out["fine_s"], out["fine_conf"] = L * 0.001, round(conf, 3)

    # drift: head / mid / tail windows of 120 s inside the overlap, 0.5 ms hop, ±100 ms
    r05, c05 = envelope(ref, 4, 80), envelope(cam, 4, 80)
    o = out["fine_s"]
    ov_lo = max(0.0, o)
    ov_hi = min(len(ref) / SR, o + len(cam) / SR)
    W = min(120.0, (ov_hi - ov_lo) / 3)
    wins = []
    for frac in (0.0, 0.5, 1.0):
        a = ov_lo + frac * (ov_hi - ov_lo - W)
        Lw, cw = local_lag(r05, c05, round(o / 0.0005), 200, int(a / 0.0005), int((a + W) / 0.0005))
        if Lw is not None:
            wins.append({"at_s": round(a + W / 2, 1), "offset_s": Lw * 0.0005, "conf": round(cw, 3)})
    out["windows"] = wins
    good = [w for w in wins if w["conf"] >= 0.3]
    mid = next((w for w in wins if w is wins[len(wins) // 2] and w["conf"] >= 0.3), None)
    out["offset_s"] = (mid or (good[0] if good else {"offset_s": o}))["offset_s"]
    offs = [w["offset_s"] for w in good]
    out["drift_ms"] = round((max(offs) - min(offs)) * 1000, 2) if len(offs) > 1 else None
    return out


# ---------- xmeml ----------

R = "<rate><timebase>30</timebase><ntsc>TRUE</ntsc></rate>"


def pathurl(p):
    return "file://localhost" + quote(str(p))   # quote() encodes ' '->%20 and '#'->%23


def build_xml(name, mics, vids, mic_dur, mic_meta):
    """mics: [(key, path)], vids: [(key, path, summary, offset_s)] in track order."""
    fr = lambda t: int(round(t * FPS))
    mic0 = max([0] + [-fr(o) for *_, o in vids])
    miclen = int(mic_dur * FPS)
    rows = []
    for key, path, s, o in vids:
        start = mic0 + fr(o)
        length = int(s["duration"] * FPS)
        rows.append(dict(key=key, path=path, s=s, o=o, start=start, len=length,
                         err_ms=((start - mic0) / FPS - o) * 1000))
    seqlen = max([r["start"] + r["len"] for r in rows] + [mic0 + miclen])

    def vfile(r):
        s = r["s"]; v = s["video"]; a = s.get("audio", {})
        tb, ntsc = media.xml_rate(v["fps"])
        nf = int(round(s["duration"] * v["fps"]))
        return (f'<file id="file-{r["key"]}"><name>{Path(r["path"]).name}</name><pathurl>{pathurl(r["path"])}</pathurl>'
                f'<rate><timebase>{tb}</timebase><ntsc>{"TRUE" if ntsc else "FALSE"}</ntsc></rate><duration>{nf}</duration>'
                f'<media><video><samplecharacteristics><width>{v["width"]}</width><height>{v["height"]}</height></samplecharacteristics></video>'
                f'<audio><samplecharacteristics><depth>16</depth><samplerate>{a.get("sample_rate", 48000)}</samplerate></samplecharacteristics>'
                f'<channelcount>{a.get("channels", 2)}</channelcount></audio></media></file>')

    vtr = {r["key"]: i + 1 for i, r in enumerate(rows)}
    atr = {r["key"]: i + 1 + len(mics) for i, r in enumerate(rows)}
    seen = set()

    def fileref(key, full):
        if key in seen:
            return f'<file id="file-{key}"/>'
        seen.add(key)
        return full

    def links(k):
        return (f'<link><linkclipref>{k}-v</linkclipref><mediatype>video</mediatype><trackindex>{vtr[k]}</trackindex><clipindex>1</clipindex></link>'
                f'<link><linkclipref>{k}-a1</linkclipref><mediatype>audio</mediatype><trackindex>{atr[k]}</trackindex><clipindex>1</clipindex><groupindex>1</groupindex></link>')

    def vclip(r, kind):
        k, L = r["key"], r["len"]
        en = "TRUE" if kind == "v" else "FALSE"
        extra = "" if kind == "v" else "<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>"
        return (f'<clipitem id="{k}-{kind}"><masterclipid>mc-{k}</masterclipid><name>{Path(r["path"]).name}</name>'
                f'<enabled>{en}</enabled><duration>{L}</duration>{R}<start>{r["start"]}</start><end>{r["start"] + L}</end>'
                f'<in>0</in><out>{L}</out>{fileref(k, vfile(r))}{extra}{links(k)}</clipitem>')

    def mclip(key, path):
        m = mic_meta[key]
        full = (f'<file id="file-{key}"><name>{Path(path).name}</name><pathurl>{pathurl(path)}</pathurl>{R}'
                f'<duration>{miclen}</duration><media><audio><samplecharacteristics><depth>{m["bits"]}</depth>'
                f'<samplerate>{m["sample_rate"]}</samplerate></samplecharacteristics><channelcount>{m["channels"]}</channelcount></audio></media></file>')
        return (f'<clipitem id="{key}"><masterclipid>mc-{key}</masterclipid><name>{Path(path).name}</name><enabled>TRUE</enabled>'
                f'<duration>{miclen}</duration>{R}<start>{mic0}</start><end>{mic0 + miclen}</end><in>0</in><out>{miclen}</out>'
                f'{fileref(key, full)}<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')

    T = "<enabled>TRUE</enabled><locked>FALSE</locked>"
    vt = "".join(f"<track>{vclip(r, 'v')}{T}</track>" for r in rows)
    at = "".join(f"<track>{mclip(k, p)}{T}</track>" for k, p in mics)
    at += "".join(f"<track>{vclip(r, 'a1')}<enabled>FALSE</enabled><locked>FALSE</locked></track>" for r in rows)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
           f'<xmeml version="4"><sequence id="seq-main"><name>{name}</name><duration>{seqlen}</duration>{R}'
           f'<timecode>{R}<string>00:00:00;00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>'
           f'<media><video><format><samplecharacteristics>{R}<width>1920</width><height>1080</height>'
           f'<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>{vt}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
           f'<samplerate>48000</samplerate></samplecharacteristics></format>{at}</audio></media></sequence></xmeml>\n')
    ET.fromstring(xml.split("\n", 2)[2])   # well-formed check
    return xml, mic0, rows


def offsets_from_xml(xml_path, mic_key):
    """Implied source offsets (s vs mic start) read back from the written XML."""
    root = ET.parse(xml_path).getroot()
    starts = {ci.get("id"): int(ci.findtext("start")) for ci in root.iter("clipitem")}
    mic0 = starts[mic_key]
    return {cid[:-2]: (st - mic0) / FPS for cid, st in starts.items() if cid.endswith("-v")}


# ---------- run ----------

def run(episode_yaml, reference="mics", deliver=False):
    ep = yaml.safe_load(Path(episode_yaml).read_text())
    work = Path(ep["work_dir"]); cache = work / "audio"
    rel = ep["release"]
    mm, dd, yy = ep["recording_date"].split(".")
    raw = ep.get("mic_mode") == "raw_band"
    name = f"ShopTalk_{mm}-{dd}-{yy}_R{rel}_SYNCED" + ("_RAWMICS" if raw else "")

    if reference == "obs":
        raise SystemExit("OBS-reference fallback: not wired yet (mic files exist for this episode).")

    print("Extracting mic audio (8 kHz)…", flush=True)
    mics, mic_meta, tracks = [], {}, []
    for i, m in enumerate(ep["mics"], 1):
        key = f"MIC{i}"
        s = media.summarize(m["file"])
        a = s["audio"]
        mic_meta[key] = {"bits": int(a.get("bits") or 24), "sample_rate": a["sample_rate"], "channels": a["channels"]}
        x = media.extract_audio(m["file"], cache, SR, channel=0, tag=key)
        peak = float(np.max(np.abs(x)))
        if peak > 0.99:
            print(f"  ! {key} peaks at {peak:.3f}: possible clipping")
        tracks.append(x / (np.sqrt(np.mean(x * x)) + 1e-9))
        mics.append((key, m["file"]))
    n = min(len(t) for t in tracks)
    ref = np.sum([t[:n] for t in tracks], axis=0).astype(np.float32)
    mic_dur = media.summarize(ep["mics"][0]["file"])["duration"]

    order = {"ave": 0, "093a": 1, "wide": 2, "video": 3}
    cams = sorted(ep["cameras"], key=lambda c: order.get(c["kind"], 9))
    sources = [(Path(c["file"]).stem.replace(" ", "_"), c["file"]) for c in cams]
    sources += [("OBS", p) for p in ep.get("obs", [])]

    report, vids = {}, []
    for key, path in sources:
        print(f"Measuring {Path(path).name}…", flush=True)
        s = media.summarize(path)
        cam = media.extract_audio(path, cache, SR, channel=0, tag=key)
        res = measure(ref, cam)
        report[Path(path).name] = res
        flag = "" if res["fine_conf"] >= 0.5 else "   ! LOW CONFIDENCE, check by eye"
        print(f"  coarse {res['coarse_s']:+.2f}s conf {res['coarse_conf']}  fine {res['fine_s']:+.4f}s  "
              f"offset {res['offset_s']:+.4f}s  drift {res['drift_ms']} ms{flag}")
        vids.append((key, path, s, res["offset_s"]))

    xml, mic0, rows = build_xml(name, mics, vids, mic_dur, mic_meta)
    out = work / f"{name}.xml"
    out.write_text(xml)

    # re-measure from the written XML at head / mid / tail
    print("\nRe-measuring from the written XML…")
    implied = offsets_from_xml(out, "MIC1")
    for key, path, s, o in vids:
        cam = media.extract_audio(path, cache, SR, channel=0, tag=key)
        res = measure(ref, cam, expect=implied[key])
        resid = [round((w["offset_s"] - implied[key]) * 1000, 1) for w in res["windows"] if w["conf"] >= 0.3]
        report[Path(path).name]["xml_offset_s"] = round(implied[key], 5)
        report[Path(path).name]["xml_residual_ms"] = resid
        worst = max(map(abs, resid)) if resid else None
        ok = "OK" if worst is not None and worst <= 20 else "CHECK"
        print(f"  {Path(path).name:28s} placed {implied[key]:+.4f}s  residuals {resid} ms  {ok}")

    (work / "sync_report.yaml").write_text(yaml.safe_dump(report, sort_keys=False))
    print(f"\nMic start frame {mic0}; sequence {max(r['start'] + r['len'] for r in rows) / FPS / 60:.1f} min")
    print(f"XML:    {out}\nReport: {work / 'sync_report.yaml'}")

    if deliver:
        dest = Path(ep["recording_folder"]) / out.name
        if dest.exists():
            raise SystemExit(f"Not delivering: {dest} already exists (never overwrite). Rename or move the old one to _to_delete/.")
        shutil.copy2(out, dest)
        if not filecmp.cmp(out, dest, shallow=False):
            raise SystemExit(f"Copy verify FAILED for {dest}")
        print(f"Delivered: {dest}")
    return report
