"""Local prep for transcripts: a one-page outline instead of the full words.json.

  .venv/bin/python scripts/transcript_outline.py words.json [--chunk 45] [--out outline.md]
  .venv/bin/python scripts/transcript_outline.py words.json --find "pearl diver" [--find ...]

Outline: one line per ~chunk seconds (speaker turns kept), the opening words of
each line, plus long pauses. --find prints exact word times with a little context,
so a cut point never needs the full transcript.
"""
import argparse, json, re
from pathlib import Path


def ts(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def norm(w):
    return re.sub(r"[^\w']", "", w.lower())


def outline(words, chunk, head):
    lines, cur = [], []
    for w in words:
        if cur and w["t0"] - cur[0]["t0"] >= chunk:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    out = []
    for c in lines:
        spks = list(dict.fromkeys(w["spk"] for w in c if w.get("spk")))
        spk = f"[{'/'.join(spks)}] " if spks else ""
        text = " ".join(w["w"] for w in c[:head]) + (" …" if len(c) > head else "")
        out.append(f"{ts(c[0]['t0'])}-{ts(c[-1]['t1'])} {spk}{text}")
    return out


def find(words, phrase, ctx=6):
    target = [norm(p) for p in phrase.split()]
    keys = [norm(w["w"]) for w in words]
    hits = []
    for i in range(len(keys) - len(target) + 1):
        if keys[i:i + len(target)] == target:
            a, b = words[i], words[i + len(target) - 1]
            before = " ".join(w["w"] for w in words[max(0, i - ctx):i])
            after = " ".join(w["w"] for w in words[i + len(target):i + len(target) + ctx])
            hits.append(f"{a['t0']:.2f}-{b['t1']:.2f}  …{before} [{' '.join(w['w'] for w in words[i:i + len(target)])}] {after}…")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words")
    ap.add_argument("--chunk", type=float, default=45, help="seconds per outline line")
    ap.add_argument("--head", type=int, default=14, help="words shown per line")
    ap.add_argument("--pause", type=float, default=2.0, help="list gaps longer than this")
    ap.add_argument("--find", action="append", help="phrase to locate (repeatable)")
    ap.add_argument("--out", help="write outline here (default: next to words.json)")
    a = ap.parse_args()
    src = Path(a.words).expanduser()
    words = json.loads(src.read_text())

    if a.find:
        for ph in a.find:
            hits = find(words, ph)
            print(f"## {ph}: {len(hits)} hit(s)")
            print("\n".join(hits[:20]) or "  none")
        return

    body = outline(words, a.chunk, a.head)
    gaps = [f"{ts(p['t1'])} {n['t0'] - p['t1']:.1f}s" for p, n in zip(words, words[1:]) if n["t0"] - p["t1"] > a.pause]
    dur = words[-1]["t1"] if words else 0
    text = "\n".join([f"# {src.name}: {len(words)} words, {ts(dur)}", "",
                      "Use --find \"phrase\" for exact word times.", "", *body, "",
                      f"## Pauses > {a.pause:g}s ({len(gaps)})", ", ".join(gaps[:60])]) + "\n"
    out = Path(a.out).expanduser() if a.out else src.with_name(src.name.replace(".json", "") + ".outline.md")
    out.write_text(text)
    print(out)


if __name__ == "__main__":
    main()
