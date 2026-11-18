"""nljbs command line."""
import argparse


def main():
    ap = argparse.ArgumentParser(prog="nljbs")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="inventory a recording folder, draft episode.yaml")
    p.add_argument("folder")
    p.add_argument("--work")

    s = sub.add_parser("sync", help="measure offsets and write the _SYNCED.xml")
    s.add_argument("episode", help="episode.yaml from `nljbs probe`")
    s.add_argument("--reference", choices=["mics", "obs"], default="mics")
    s.add_argument("--deliver", action="store_true",
                   help="copy the XML into the recording folder (new filename only, never overwrites)")

    t = sub.add_parser("transcribe", help="Parakeet ASR on the mics -> words.json, transcript.txt, levels.npy")
    t.add_argument("episode")

    sc = sub.add_parser("screen", help="OBS screen states + IG image boxes -> screen.json")
    sc.add_argument("episode")

    sw = sub.add_parser("switcher", help="full auto edit from an episodes/R<NN>_edit.yaml -> _SWITCHER.xml")
    sw.add_argument("edit")
    sw.add_argument("--deliver", action="store_true", help="copy XML + plates to the recording folder (new names only)")
    sw.add_argument("--variant", help="name suffix, e.g. GRADED -> ..._SWITCHER_GRADED.xml")

    li = sub.add_parser("lint", help="check an xmeml against the Premiere invariants")
    li.add_argument("xml")

    gr = sub.add_parser("grade", help="bake LUT + grade into <stem>_GRADED.mp4 per camera")
    gr.add_argument("edit")
    gr.add_argument("--deliver", action="store_true", help="copy graded files to the recording folder")
    gr.add_argument("--only", nargs="*", help="camera stems to do (default all)")

    lu = sub.add_parser("luts", help="one finished .cube per camera (LUT + finish combined)")
    lu.add_argument("edit")
    lu.add_argument("--deliver", help="folder to copy the .cube files into (never overwrites)")

    a = ap.parse_args()
    if a.cmd == "luts":
        from . import luts
        luts.run(a.edit, deliver_dir=a.deliver)
        return
    if a.cmd == "grade":
        from . import grade
        grade.run(a.edit, deliver=a.deliver, only=a.only)
        return
    if a.cmd == "lint":
        from . import lint
        raise SystemExit(0 if lint.run(a.xml) else 1)
    if a.cmd == "switcher":
        from . import switcher
        switcher.run(a.edit, deliver=a.deliver, variant=a.variant)
        return
    if a.cmd == "screen":
        from . import screen
        screen.run(a.episode)
        return
    if a.cmd == "transcribe":
        from . import transcribe
        transcribe.run(a.episode)
        return
    if a.cmd == "probe":
        from . import probe
        probe.run(a.folder, a.work)
    elif a.cmd == "sync":
        from . import sync
        sync.run(a.episode, reference=a.reference, deliver=a.deliver)


if __name__ == "__main__":
    main()
