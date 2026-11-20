"""palefire command line."""
import argparse


def main():
    ap = argparse.ArgumentParser(prog="palefire")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="inventory a shoot folder, flag oddities, draft shoot.yaml + contact sheet")
    p.add_argument("folder")
    p.add_argument("--work", help="work dir (default ~/r3-work/palefire/<slug>)")
    p.add_argument("--no-sheet", action="store_true", help="skip the contact sheet")

    c = sub.add_parser("cut", help="build vertical reels from a shoots/<date>.yaml cut plan: XML + SRT (+ preview)")
    c.add_argument("plan")
    c.add_argument("ids", nargs="*", help="reel ids to build (default all)")
    c.add_argument("--preview", action="store_true", help="also render a graded preview MP4 with the music mix")

    s = sub.add_parser("social", help="export <id>_SOCIAL.mp4 from <id>_FINAL.mp4 to Instagram/Facebook Reels spec")
    s.add_argument("plan")
    s.add_argument("ids", nargs="*", help="reel ids (default all)")

    v = sub.add_parser("serve", help="short-lived public links (Cloudflare quick tunnel) for Rella to import videos")
    v.add_argument("files", nargs="+")
    v.add_argument("--minutes", type=float, default=10, help="close after this long (default 10)")

    a = ap.parse_args()
    if a.cmd == "social":
        from . import social
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
