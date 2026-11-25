"""palefire command line."""
import argparse


def main():
    ap = argparse.ArgumentParser(prog="palefire")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="inventory a shoot folder, flag oddities, draft shoot.yaml + contact sheet")
    p.add_argument("folder")
    p.add_argument("--work", help="work dir (default ~/r3-work/palefire/<slug>)")
    p.add_argument("--no-sheet", action="store_true", help="skip the contact sheet")

    t = sub.add_parser("transcribe", help="Parakeet word timings per camera clip -> <work>/transcripts/")
    t.add_argument("folder", help="shoot folder (clips in its RAW VIDEO subfolder)")
    t.add_argument("stems", nargs="*", help="clip names without extension (default all)")
    t.add_argument("--work", help="work dir (default ~/r3-work/palefire/<slug>, same as probe)")
    t.add_argument("--force", action="store_true", help="redo clips that already have a transcript")

    b = sub.add_parser("beats", help="Beat This beats + downbeats for <shoot>/music -> <work>/music/*.beats.json")
    b.add_argument("folder", help="shoot folder (tracks in its music subfolder)")
    b.add_argument("--work", help="work dir (default ~/r3-work/palefire/<slug>, same as probe)")
    b.add_argument("--force", action="store_true", help="redo tracks that already have a beats file")

    m = sub.add_parser("music", help="shared music library: index it once, then pick tracks for a reel")
    msub = m.add_subparsers(dest="mcmd", required=True)
    mi = msub.add_parser("index", help="analyze new tracks -> ~/r3-work/music/index.json")
    mi.add_argument("--library", help="library folder (default /Volumes/Extreme SSD/MUSIC LIBRARY or $R3_MUSIC)")
    mi.add_argument("--force", action="store_true", help="re-analyze every track")
    mp = msub.add_parser("pick", help="rank tracks for a reel")
    mp.add_argument("--tag", help="library folder name, e.g. party-upbeat")
    mp.add_argument("--bpm", help="tempo range, e.g. 105-125")
    mp.add_argument("--min", type=float, default=60, help="shortest usable track in seconds (default 60)")
    mp.add_argument("--client", help="skip tracks this client used recently, e.g. 'PALE FIRE'")
    mp.add_argument("--days", type=int, default=60, help="how recent counts as recent (default 60)")
    mp.add_argument("--break", dest="need_break", action="store_true", help="only tracks with a break")

    c = sub.add_parser("cut",help="build vertical reels from a shoots/<date>.yaml cut plan: XML + SRT (+ preview)")
    c.add_argument("plan")
    c.add_argument("ids", nargs="*", help="reel ids to build (default all)")
    c.add_argument("--preview", action="store_true", help="also render a graded preview MP4 with the music mix")

    s = sub.add_parser("social", help="export <id>_SOCIAL.mp4 to Instagram/Facebook Reels spec at -14 LUFS, from a "
                                      "shoot plan's <id>_FINAL.mp4 or from finished MP4s")
    s.add_argument("plan", help="shoots/<date>.yaml, or one or more finished .mp4 files")
    s.add_argument("ids", nargs="*", help="reel ids (default all), or more .mp4 files")
    s.add_argument("--out", help="where MP4 inputs' _SOCIAL files go (default ~/r3-work/social)")
    s.add_argument("--instagram", action="store_true",
                   help="Instagram only: allow up to 15 min (Facebook Reels stop at 90 s)")

    v = sub.add_parser("serve", help="short-lived public links (Cloudflare quick tunnel) for Rella to import videos")
    v.add_argument("files", nargs="+")
    v.add_argument("--minutes", type=float, default=10, help="close after this long (default 10)")

    a = ap.parse_args()
    if a.cmd == "music":
        from . import music
        if a.mcmd == "index":
            music.run_index(a.library, a.force)
        else:
            music.run_pick(a.tag, a.bpm, a.min, a.client, a.days, a.need_break)
        return
    if a.cmd == "transcribe":
        from . import transcribe
        transcribe.run(a.folder, a.work, a.stems, a.force)
        return
    if a.cmd == "beats":
        from . import beats
        beats.run(a.folder, a.work, a.force)
        return
    if a.cmd == "social":
        from . import social
        if a.instagram:
            social.SPEC["dur"] = (3.0, 900.0)
        if a.plan.lower().endswith(".mp4"):
            social.run_files([a.plan] + a.ids, a.out)
        else:
            social.run_social(a.plan, a.ids)
        return
    if a.cmd == "serve":
        from . import social
        social.serve(a.files, a.minutes)
        return
    if a.cmd == "cut":
        from . import cut
        cut.run(a.plan, a.ids, preview=a.preview)
        return
    if a.cmd == "probe":
        from . import probe
        probe.run(a.folder, a.work, sheet=not a.no_sheet)


if __name__ == "__main__":
    main()
