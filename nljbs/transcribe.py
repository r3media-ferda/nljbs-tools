"""`nljbs transcribe <episode.yaml>`: Parakeet ASR on the mic mix -> words with timing + speaker.

Outputs in the work dir:
  words.json      [{"w", "t0", "t1", "spk"}]  times in seconds on the mic timeline
  levels.npy      (n_mics, frames) band level dB, 150-3500 Hz, 10 ms hop, frame i covers i*0.01 .. +0.05
  transcript.txt  readable, one line per turn: "  12:34.5  PORTER  text…"
"""
import json
import time
from pathlib import Path

import numpy as np
import yaml

from . import media

SR = 16000
MODEL = media.WORK_ROOT / "models" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"


def band_levels(x, win=800, hop=160):
    """150-3500 Hz band power in dB per 10 ms hop (50 ms Hann window)."""
    n = (len(x) - win) // hop
    out = np.zeros(n, np.float32)
    w = np.hanning(win).astype(np.float32)
    f = np.fft.rfftfreq(win, 1 / SR)
    m = (f >= 150) & (f <= 3500)
    for s in range(0, n, 20000):
        idx = np.arange(s, min(n, s + 20000))[:, None] * hop + np.arange(win)
        F = np.abs(np.fft.rfft(x[idx] * w, axis=1))[:, m] ** 2
        out[s:s + len(F)] = 10 * np.log10(F.mean(1) + 1e-12)
    return out


def chunk_points(x):
    """Cut points at the quietest spot every 18-28 s."""
    e = np.sqrt(np.convolve(x ** 2, np.ones(1600) / 1600, "same")[::160])
    cuts, t, dur = [0.0], 0.0, len(x) / SR
    while t < dur - 28:
        lo, hi = int((t + 18) * 100), int((t + 28) * 100)
        t = (lo + int(np.argmin(e[lo:hi]))) / 100
        cuts.append(t)
    cuts.append(dur)
    return cuts


def asr(x, threads=8):
    import sherpa_onnx
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(MODEL / "encoder.int8.onnx"), decoder=str(MODEL / "decoder.int8.onnx"),
        joiner=str(MODEL / "joiner.int8.onnx"), tokens=str(MODEL / "tokens.txt"),
        model_type="nemo_transducer", num_threads=threads)
    cuts = chunk_points(x)
    words = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        s = rec.create_stream()
        s.accept_waveform(SR, x[int(a * SR):int(b * SR)])
        rec.decode_stream(s)
        cur = None
        for tk, tt in zip(s.result.tokens, s.result.timestamps):
            if tk.startswith(" ") or cur is None:      # Parakeet tokens open a word with a plain space
                if cur:
                    words.append(cur)
                cur = [tk.strip(), round(a + tt, 3)]
            else:
                cur[0] += tk
        if cur:
            words.append(cur)
    words = [w for w in words if w[0]]
    out = []
    for i, (w, t) in enumerate(words):
        nxt = words[i + 1][1] if i + 1 < len(words) else t + 1.0
        out.append({"w": w, "t0": t, "t1": round(min(nxt - 0.02, t + 0.10 + 0.07 * len(w)), 3)})
    return out


def speakers(words, L, lead_db=5.0):
    """Loudest mic inside each word must lead by lead_db, else inherit. 1-word islands folded."""
    prev, spk = 0, []
    for i, w in enumerate(words):
        a = w["t0"] + 0.02
        b = max(min(words[i + 1]["t0"] if i + 1 < len(words) else a + 0.45, w["t0"] + 0.45), a + 0.06)
        fa, fb = int((a - 0.025) * 100), int((b - 0.025) * 100) + 1
        seg = L[:, max(0, fa):fb]
        lv = 10 * np.log10(np.mean(10 ** (seg / 10), axis=1))
        o = np.argsort(lv)[::-1]
        s = int(o[0]) if lv[o[0]] - lv[o[1]] > lead_db else prev
        spk.append(s)
        prev = s
    for i in range(1, len(spk) - 1):
        if spk[i - 1] == spk[i + 1] != spk[i]:
            spk[i] = spk[i - 1]
    return spk


def fmt_t(t):
    return f"{int(t // 60):3d}:{t % 60:04.1f}"


def run(episode_yaml):
    ep = yaml.safe_load(Path(episode_yaml).read_text())
    work = Path(ep["work_dir"])
    cache = work / "audio"
    names = [(m.get("who") or f"MIC{i}").upper() for i, m in enumerate(ep["mics"], 1)]
    fix = ep.get("asr_fix", {}) or {}

    tracks = []
    for i, m in enumerate(ep["mics"], 1):
        tag = f"MIC{i}_{Path(m['file']).stem.replace(' ', '_')}"
        tracks.append(media.extract_audio(m["file"], cache, SR, channel=0, tag=tag))
    n = min(len(t) for t in tracks)
    tracks = [t[:n] for t in tracks]

    t0 = time.time()
    L = np.stack([band_levels(t) for t in tracks])
    np.save(work / "levels.npy", L)

    x = np.sum(tracks, axis=0)
    x *= 0.3 / (np.percentile(np.abs(x), 99.9) + 1e-9)
    print(f"ASR on {n / SR / 60:.1f} min mix…", flush=True)
    words = asr(x.astype(np.float32))
    spk = speakers(words, L)
    for w, s in zip(words, spk):
        w["spk"] = names[s]
    (work / "words.json").write_text(json.dumps(words))

    lines, cur = [], None
    for w in words:
        if cur is None or w["spk"] != cur[1] or len(cur[2]) > 45:
            if cur:
                lines.append(cur)
            cur = [w["t0"], w["spk"], []]
        cur[2].append(w["w"])
    lines.append(cur)
    text = []
    for t, s, ws in lines:
        line = " ".join(ws)
        for bad, good in fix.items():
            line = line.replace(bad, good)
        text.append(f"{fmt_t(t)}  {s:7s} {line}")
    (work / "transcript.txt").write_text("\n".join(text) + "\n")

    from collections import Counter
    c = Counter(spk)
    print(f"{len(words)} words in {time.time() - t0:.0f}s; per speaker: " +
          ", ".join(f"{names[k]} {v}" for k, v in sorted(c.items())))
    print(f"Transcript: {work / 'transcript.txt'}")
