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

    a = ap.parse_args()
    if a.cmd == "probe":
        from . import probe
        probe.run(a.folder, a.work)
    elif a.cmd == "sync":
        from . import sync
        sync.run(a.episode, reference=a.reference, deliver=a.deliver)


if __name__ == "__main__":
    main()
