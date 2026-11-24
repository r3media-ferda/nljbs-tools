"""`nljbs levels <edit.yaml>`: speaker-matched, YouTube-ready mic files for the switcher.

Per mic: 70 Hz high-pass + gentle compression, then a gain so each host's own speech sits at the same
loudness. One common gain then brings the cut (cold open + body, mics only, from the switcher plan) to
-14 LUFS integrated (YouTube's playback reference) and a limiter holds true peak at -1.5 dBTP.

Writes <work>/levels/mic N_R<NN>_LEVEL.wav (44.1 kHz 24-bit mono, sample-aligned with the originals; the
limiter runs with latency compensation and the alignment is measured) plus levels_report.yaml.
Point the switcher at them with `mic_files:` in the edit config, rebuild, and re-run this to verify.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import yaml

from . import media
from .switcher import FPS, speaker_runs

SR = 44100
TARGET_I, TARGET_TP = -14.0, -1.5
def comp_gain(m, thr_db=-26.0, ratio=3.0, rms_ms=10.0, smooth_ms=20.0):
    """Mix-bus RMS compressor gain curve (feed-forward, hold+average smoothing, no look-behind lag)."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    p = uniform_filter1d((m * m).astype(np.float32), int(SR * rms_ms / 1000))
    lev = 10 * np.log10(np.maximum(p, 0) + 1e-12)          # float32 filtering can dip just below 0
    gr = -(1 - 1 / ratio) * np.maximum(0.0, lev - thr_db)
    S = int(SR * smooth_ms / 1000)
    gr = uniform_filter1d(minimum_filter1d(gr, S), S)
    return (10 ** (gr / 20)).astype(np.float32)


def true_peak(m, chunk=SR * 30):
    """Per-sample true-peak estimate: max |x| over the 4x-oversampled points around each sample."""
    from scipy.signal import resample_poly
    out = np.empty(len(m), np.float32); pad = 64
    for s in range(0, len(m), chunk):
        a, b = max(0, s - pad), min(len(m), s + chunk + pad)
        u = np.abs(resample_poly(m[a:b], 4, 1)).reshape(-1, 4).max(1)
        out[s:min(len(m), s + chunk)] = u[s - a:s - a + min(chunk, len(m) - s)]
    return np.maximum(out, np.abs(m))


def limiter_gain(m, look_ms=2.0, ceiling_db=TARGET_TP - 0.3, release_ms=15.0):
    """Look-ahead brickwall gain curve for signal m, detecting on 4x-oversampled true peak
    (<= 1 everywhere, never above what each sample needs)."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    c = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, c / np.maximum(true_peak(m), 1e-9))
    L = max(1, int(SR * look_ms / 1000))
    h = minimum_filter1d(need, 2 * L + 1)                     # hold the reduction across the look-ahead
    R = max(1, int(SR * release_ms / 1000))
    h = minimum_filter1d(h, R)                                # hold ~release_ms around each peak (no pumping)
    return np.minimum(uniform_filter1d(h, L + 1), need).astype(np.float32)


def measure_lag(a, b, span=8):
    """Sample lag of b vs a over a few 8 s windows (0 = aligned)."""
    out = []
    for c in (0.25, 0.5, 0.75):
        i = int(c * len(a)); w = a[i:i + SR * span]; v = b[i - 300:i + SR * span + 300]
        xc = np.correlate(v, w, "valid"); out.append(int(np.argmax(xc)) - 300)
    return out


def decode(path, af=None):
    cmd = [media.FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR)]
    if af:
        cmd += ["-af", af]
    out = subprocess.run(cmd + ["-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32)


def write_wav(x, path, af=None):
    cmd = [media.FFMPEG, "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-"]
    if af:
        cmd += ["-af", af]
    subprocess.run(cmd + ["-c:a", "pcm_s24le", str(path)], input=x.astype(np.float32).tobytes(), check=True)


def loudness(x):
    """(integrated LUFS, true peak dBTP) of a mono float signal via ffmpeg ebur128."""
    r = subprocess.run([media.FFMPEG, "-nostdin", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       input=x.astype(np.float32).tobytes(), capture_output=True).stderr.decode()
    s = r[r.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", s).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", s).group(1))
    return i, tp


def cut_ranges(plan, B0f):
    """Sample ranges of the mic timeline that the switcher keeps: cold open then body, in timeline order."""
    segs = [(t["ga"], t["gb"]) for t in plan["TR"]] + [(a, b) for a, b, _ in plan["KEPT"]]
    return [(int(round((B0f + a) / FPS * SR)), int(round((B0f + b) / FPS * SR))) for a, b in segs]


def run(edit_yaml):
    E = yaml.safe_load(Path(edit_yaml).read_text())
    ep = yaml.safe_load(Path(os.path.expanduser(E["episode"])).read_text())
    work = Path(ep["work_dir"]); rel = E["release"]; mm, dd, yy = ep["recording_date"].split(".")
    plan_p = work / f"ShopTalk_{mm}-{dd}-{yy}_R{rel}_SWITCHER_plan.json"
    plan = json.loads(plan_p.read_text())
    B0f = int(round(E["body"][0] * FPS))
    ranges = cut_ranges(plan, B0f)
    names = [m["who"].upper() for m in ep["mics"]]
    out_dir = work / "levels"; out_dir.mkdir(exist_ok=True)

    # 1. high-pass each mic, gain so every host's own speech sits at -20 LUFS (hosts matched to each other)
    runs, _ = speaker_runs(np.load(work / "levels.npy"), names, *E["body"])
    own_sel = lambda x, nm: np.concatenate([x[int(a * SR):int(b * SR)] for a, b, s in runs if s == nm])
    comp, raw_own = [], []
    for i, m in enumerate(ep["mics"]):
        x = decode(m["file"], "highpass=f=70")
        raw_own.append(loudness(own_sel(x, names[i]))[0])
        comp.append(x * 10 ** ((-20.0 - raw_own[-1]) / 20))
        print(f"mic {i + 1} {names[i]}: own speech raw {raw_own[-1]:.1f} LUFS -> {-20.0 - raw_own[-1]:+.1f} dB",
              flush=True)
    n = min(len(x) for x in comp); comp = [x[:n] for x in comp]
    g_spk = [1.0] * len(comp)

    # 2. common gain, then compressor + limiter gain curves computed on the summed mix and applied to
    #    every mic (Premiere sums the tracks linearly, so the sum it plays gets exactly this processing)
    def cut(x):
        return np.concatenate([x[a:b] for a, b in ranges if b <= n])
    xs = [c * g for c, g in zip(comp, g_spk)]
    mixed = sum(xs)
    cg = comp_gain(mixed)                                   # compressor sees the mix at its natural level
    Ic, _ = loudness(cut(mixed * cg))
    G = 10 ** ((TARGET_I - Ic) / 20)                       # makeup after the compressor
    for it in range(4):                                    # only the limiter reacts to G: converges fast
        lg = limiter_gain(mixed * cg * G); env = cg * G * lg
        I, tp = loudness(cut(mixed * env))
        print(f"   pass {it + 1}: makeup {20 * np.log10(G):+.1f} dB  cut mix {I:.1f} LUFS  TP {tp:.1f} dBTP",
              flush=True)
        if abs(I - TARGET_I) <= 0.2:
            break
        G *= 10 ** ((TARGET_I - I) / 20)
    report_lim = lg
    finals, report = [], {"target": {"I": TARGET_I, "TP": TARGET_TP}, "mics": []}
    for i, m in enumerate(ep["mics"]):
        dst = out_dir / f"mic {i + 1}_R{rel}_LEVEL.wav"
        write_wav(xs[i] * env, dst)
        y = decode(dst); finals.append(y[:n])
        lag = measure_lag(decode(m["file"], "highpass=f=70")[:n], y[:n])
        gain_db = 20 * np.log10(g_spk[i] * G) + (-20.0 - raw_own[i])      # before the shared dynamics
        report["mics"].append({"file": str(dst), "who": names[i], "own_speech_raw_lufs": round(raw_own[i], 1),
                               "gain_db": round(float(gain_db), 2), "lag_samples": lag,
                               "samples": int(len(y)), "orig_samples": int(n)})
        print(f"   {dst.name}: gain {gain_db:+.1f} dB  lag {lag} samples", flush=True)
    report["limiter_max_reduction_db"] = round(float(-20 * np.log10(report_lim.min())), 1)
    report["limiter_time_over_3db_s"] = round(float((report_lim < 10 ** (-3 / 20)).sum() / SR), 1)

    # 3. verify the cut mix from the written files
    I1, tp1 = loudness(cut(sum(finals)))
    report["cut_mix"] = {"I": I1, "TP": tp1, "ok": abs(I1 - TARGET_I) <= 0.5 and tp1 <= -1.0}
    (work / "levels_report.yaml").write_text(yaml.safe_dump(report, sort_keys=False))
    print(f"cut mix after: {I1:.1f} LUFS  TP {tp1:.1f} dBTP  {'OK' if report['cut_mix']['ok'] else 'CHECK'}")
    return report
