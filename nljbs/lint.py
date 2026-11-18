"""`nljbs lint <xml>`: check an xmeml against the handoff section 5 invariants. Exit 1 on errors."""
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

TK = 8475667200
CAM_RE = re.compile(r"^(AVE\d+|093A\d+|C\d{4})(_GRADED)?\.MP4$|^\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}\.mp4$", re.I)


def run(path):
    root = ET.parse(path).getroot()
    errs, warns = [], []
    files = {f.get("id"): f for f in root.iter("file") if len(f)}

    for s in root.iter("sequence"):
        r = s.find("rate")
        if r is not None and (r.findtext("timebase") != "30" or r.findtext("ntsc") != "TRUE"):
            errs.append(f"sequence {s.findtext('name')}: rate is not 29.97 NTSC")

    for c in root.iter("clipitem"):
        nm = c.findtext("name") or ""
        r = c.find("rate")
        fe = c.find("file")
        f = files.get(fe.get("id")) if fe is not None else None
        fname = f.findtext("name") if f is not None else ""
        media_clip = nm.startswith("ANG ") or bool(CAM_RE.match(fname or "")) or (fname or "").lower().endswith((".wav", ".png"))
        tb, ntsc = (int(r.findtext("timebase")), r.findtext("ntsc") == "TRUE") if r is not None else (30, True)
        if media_clip and (tb != 30 or not ntsc):
            errs.append(f"clip {nm}: clip rate not 29.97 NTSC")
        if fname and CAM_RE.match(fname) and nm != fname:
            errs.append(f"clip named {nm!r} uses {fname}: camera/OBS clipitem name must equal the file name")
        pin, pout = c.findtext("pproTicksIn"), c.findtext("pproTicksOut")
        if pin is not None and c.findtext("in") is not None:
            tk = 254016000000 * (1001 / 1000 if ntsc else 1) / tb      # ticks per frame at this clip's own rate
            # Premiere's own graphics carry sub-frame tick edges; anything past half a frame is a real mismatch
            if abs(int(pin) - int(c.findtext("in")) * tk) > tk / 2 or abs(int(pout) - int(c.findtext("out")) * tk) > tk / 2:
                msg = f"clip {nm}: pproTicks disagree with in/out ({c.get('id')})"
                # Premiere-made graphics (time-remapped Essential Graphics) legitimately do this
                (warns if nm == "Graphic" else errs).append(msg)
        for flt in c.findall("filter"):
            if flt.findtext("effect/effectid") == "Lumetri":
                warns.append(f"clip {nm}: Lumetri in the XML (LUTs belong on source master clips)")

    for f in files.values():
        p = f.findtext("pathurl") or ""
        if " " in p or "#" in p:
            errs.append(f"file {f.findtext('name')}: pathurl not percent-encoded")
        if p and not p.startswith("file://localhost/"):
            warns.append(f"file {f.findtext('name')}: pathurl not file://localhost/")

    main = root.find("sequence")
    vt = main.findall("media/video/track")
    if vt:
        v1 = [c for c in vt[0].findall("clipitem") if (c.findtext("name") or "").startswith("ANG ")]
        if v1 and not all(c.findtext("name").startswith("ANG 1 ") for c in v1):
            errs.append("V1 holds a nest other than ANG 1 (track bump from a ripple cut?)")
        dur = int(main.findtext("duration"))
        if v1 and max(int(c.findtext("end")) for c in v1) < dur - 2:
            warns.append("V1 ANG 1 does not reach the end of the timeline")

    music = Counter()
    for i, t in enumerate(main.findall("media/audio/track")):
        for c in t.findall("clipitem"):
            nm = c.findtext("name") or ""
            if nm.upper().startswith("MIC") and c.get("premiereChannelType") not in (None, "mono"):
                errs.append(f"A{i + 1} {nm}: mic not on a mono track")
            if "SHOP TALK" in nm.upper():
                music[nm] += 1
    for nm, n in music.items():
        if n > 2:
            errs.append(f"intro music {nm} appears on {n} tracks (max one stereo pair)")

    for e in errs: print("ERROR ", e)
    for w in sorted(set(warns)): print("warn  ", w)
    print(f"lint: {len(errs)} errors, {len(set(warns))} warnings  ({path})")
    return len(errs) == 0


if __name__ == "__main__":
    sys.exit(0 if run(sys.argv[1]) else 1)
