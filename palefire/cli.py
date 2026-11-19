"""palefire command line."""
import argparse


def main():
    ap = argparse.ArgumentParser(prog="palefire")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="inventory a shoot folder, flag oddities, draft shoot.yaml + contact sheet")
    p.add_argument("folder")
    p.add_argument("--work", help="work dir (default ~/r3-work/palefire/<slug>)")
    p.add_argument("--no-sheet", action="store_true", help="skip the contact sheet")

    a = ap.parse_args()
    if a.cmd == "probe":
        from . import probe
        probe.run(a.folder, a.work, sheet=not a.no_sheet)


if __name__ == "__main__":
    main()
