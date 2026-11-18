"""`nljbs render-check <xml> <t1,t2,...>`: composite frames straight from an xmeml (enabled nest + top tracks).

Times are main-timeline seconds. --remap OLD=NEW rewrites media paths (e.g. plates not yet copied to the drive).
Ported from legacy render_check.py; still images are read without -ss (ffmpeg returns nothing otherwise).
"""
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from . import media

FPS = 30000 / 1001
W, H = 1920, 1080


def params(c):
    P = dict(scale=100, cx=0, cy=0, l=0, r=0, t=0, b=0)
    for q in c.findall(".//effect/parameter"):
        pid = q.findtext("parameterid")
        if pid == "scale": P["scale"] = float(q.findtext("value"))
        if pid == "center": P["cx"] = float(q.findtext("value/horiz")); P["cy"] = float(q.findtext("value/vert"))
        if pid in ("leftcrop", "rightcrop", "topcrop", "bottomcrop"): P[pid[0]] = float(q.findtext("value"))
    return P


def run(xml_path, times, outdir, remap=None, tag="chk", luts=None, force_angle=None):
    """luts: {file name: ffmpeg filter} applied to every use of that file, like a master-clip effect.
    force_angle: '1'..'10' renders that angle nest regardless of which one is enabled."""
    r = ET.parse(xml_path).getroot(); main = r.find("sequence")
    seqs = {s.get("id"): s for s in r.iter("sequence") if s.find("media") is not None}
    fpath = {}
    for f in r.iter("file"):
        p = f.findtext("pathurl")
        if p:
            p = unquote(p).replace("file://localhost", "")
            for old, new in (remap or {}).items():
                p = p.replace(old, new)
            fpath[f.get("id")] = p

    def layers_at(seq, tf):
        out = []
        for tr in seq.findall("media/video/track"):
            if tr.findtext("enabled") != "TRUE": continue
            items = [c for c in tr if c.tag in ("clipitem", "transitionitem", "generatoritem")]
            for j, c in enumerate(items):
                if c.tag != "clipitem": continue
                nm = c.findtext("name") or ""
                if force_angle and seq is main and nm.startswith("ANG "):
                    if not nm.startswith(f"ANG {force_angle} "): continue
                elif c.findtext("enabled") != "TRUE": continue
                s, e = int(c.findtext("start")), int(c.findtext("end"))
                # -1 = edge sits inside the neighbouring transition
                if s == -1 and j > 0 and items[j - 1].tag == "transitionitem": s = int(items[j - 1].findtext("start"))
                if e == -1 and j + 1 < len(items) and items[j + 1].tag == "transitionitem": e = int(items[j + 1].findtext("end"))
                if s < 0 or e < 0: continue
                if not (s <= tf < e): continue
                sq = c.find("sequence")
                if sq is not None:
                    out += layers_at(seqs[sq.get("id")], int(c.findtext("in")) + tf - s); continue
                fe = c.find("file")
                if fe is None or fe.get("id") not in fpath:
                    if c.findtext("name"): out.append(dict(path=None, name=c.findtext("name")))
                    continue
                out.append(dict(path=fpath[fe.get("id")], name=c.findtext("name"),
                                src_t=(int(c.findtext("in")) + tf - s) / FPS, **params(c)))
        return out

    Path(outdir).mkdir(parents=True, exist_ok=True)
    outs = []
    for T in times:
        tf = int(T * FPS); canvas = np.full((H, W, 3), 40, np.float32); desc = []
        for L in layers_at(main, tf):
            if L["path"] is None:
                desc.append(f"[{L['name'][:18]}]"); continue
            st = L["path"].lower().endswith((".png", ".jpg"))
            x0 = int(L["l"] / 100 * W); x1 = int(W - L["r"] / 100 * W); y0 = int(L["t"] / 100 * H); y1 = int(H - L["b"] / 100 * H)
            s = L["scale"] / 100; cw, ch = x1 - x0, y1 - y0
            ow, oh = max(2, int(cw * s) // 2 * 2), max(2, int(ch * s) // 2 * 2)
            lut = (luts or {}).get(Path(L["path"]).name)
            vf = (lut + "," if lut else "") + f"scale=1920:1080,crop={cw}:{ch}:{x0}:{y0},scale={ow}:{oh}"
            cmd = [media.FFMPEG, "-v", "error"] + ([] if st else ["-ss", f"{L['src_t']:.3f}"]) + \
                  ["-i", L["path"], "-frames:v", "1", "-vf", vf,
                   "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
            raw = subprocess.run(cmd, capture_output=True).stdout
            if len(raw) < ow * oh * 4:
                desc.append("MISSING " + Path(L["path"]).name); continue
            img = np.frombuffer(raw, np.uint8)[:ow * oh * 4].reshape(oh, ow, 4).astype(np.float32)
            PX = W / 2 + L["cx"] * W; PY = H / 2 + L["cy"] * H
            ox = int(round(PX + (x0 - W / 2) * s)); oy = int(round(PY + (y0 - H / 2) * s))
            a0, b0 = max(0, ox), max(0, oy); a1, b1 = min(W, ox + ow), min(H, oy + oh)
            if a1 > a0 and b1 > b0:
                sub = img[b0 - oy:b1 - oy, a0 - ox:a1 - ox]; al = sub[..., 3:4] / 255
                canvas[b0:b1, a0:a1] = canvas[b0:b1, a0:a1] * (1 - al) + sub[..., :3] * al
            desc.append(f"{Path(L['path']).name[:20]}" + ("" if st else f"@{L['src_t']:.1f}"))
        fn = Path(outdir) / f"{tag}_{T:07.1f}.jpg"
        subprocess.run([media.FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080",
                        "-i", "-", "-vf", "scale=960:540", "-q:v", "4", str(fn)],
                       input=canvas.clip(0, 255).astype(np.uint8).tobytes())
        outs.append(fn)
        print(f"{T:7.1f}  " + " | ".join(desc))
    return outs


def sheet(files, out, cols=3):
    import cv2
    ims = [cv2.imread(str(f)) for f in files]
    h, w = ims[0].shape[:2]
    ims += [np.zeros_like(ims[0])] * ((-len(ims)) % cols)
    rows = [np.hstack(ims[i:i + cols]) for i in range(0, len(ims), cols)]
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
