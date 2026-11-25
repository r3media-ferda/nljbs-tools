# nljbs-tools

CLI for the NLJBS Shop Talk weekly production run. Full spec: `docs/NLJBS_CLAUDE_CODE_HANDOFF.md` (read it before changing behavior).

## Run

```bash
cd ~/Code/nljbs-tools
.venv/bin/nljbs probe "/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/<date>/RECORDING N"
.venv/bin/nljbs sync ~/nljbs-work/<date>_RECORDINGN/episode.yaml            # build + verify locally
.venv/bin/nljbs sync ~/nljbs-work/<date>_RECORDINGN/episode.yaml --deliver  # also copy XML to the recording folder
```

Python venv in `.venv` (3.15 on Oz's Mac, 3.14 on Avery's; both work). ffmpeg/ffprobe come from the `static-ffmpeg` package (no Homebrew on this Mac).
Work files (audio caches, frames, reports, draft XML) live in `~/nljbs-work/<date>_<recording>/`, never on the drive.

## Hard rules

- Never overwrite anything on `/Volumes/NLJBS Drive`. New filenames only; superseded files go to `_to_delete/` for Avery to delete.
- Render to `~/nljbs-work`, then copy to the drive and verify (md5 / byte compare).
- Heavy ffmpeg jobs run one at a time in the foreground.
- Never name a module `xml.py`.
- Artist handles come from the screen (OBS IG header) or transcript, never from memory.
- Public text (titles, captions, descriptions) in NLJBS voice: casual, shop-floor. Never the word "swag".
- Publishing is outward-facing: dry run first, Avery confirms before any real upload.
- Rella: every post goes in with status PENDING, even when scheduled. A Pale Fire staff member reviews posts before they go live; APPROVED means she signed off, so never set it and never move a post out of it. Never turn on auto-publish.

## Working together (Avery and Oz)

Two people, two Macs, one repo: `github.com/r3media-ferda/nljbs-tools`.

- Start every session with `git pull`. End every piece of work with a commit and `git push`, so the other person's Claude sees it.
- Oz's editing expertise lives in `docs/OZ_EDITING_WORKFLOW.md`. Read it before cutting anything, alongside `docs/R3_SHORT_FORM_STYLE.md`. When Oz explains how he works, write it there and commit it.
- Never commit tokens, passwords, client footage, or music audio. Footage stays on the drives; music audio stays on the Synology.

## XML (xmeml v4) invariants

29.97 NTSC everywhere (`timebase 30`, `ntsc TRUE`); clipitem `<name>` = source file name for cameras/OBS; `pathurl` as `file://localhost` + percent-encoded path (`%20`, `%23`); mics on mono tracks; camera scratch audio disabled; AVE on V1; no pproTicks in generated clips.

## Layout

- `nljbs/media.py` ffprobe/ffmpeg helpers, audio cache
- `nljbs/probe.py` folder inventory, flags, draft `episode.yaml`, contact sheet
- `nljbs/sync.py` envelope sync (coarse 10 ms / fine 1 ms / drift 0.5 ms), xmeml writer, re-measure from written XML
- `nljbs/transcribe.py` Parakeet (sherpa-onnx, model in `~/nljbs-work/models/`) -> `words.json`, `transcript.txt`, `levels.npy`
- `nljbs/screen.py` OBS stable screen states + IG image boxes (letterbox-trimmed) -> `screen.json`, review sheets
- `nljbs/switcher.py` full auto edit from `episodes/R<NN>_edit.yaml` (sections, handles, cold open, cuts, image slots) using the last finished edit as template
- `nljbs/lint.py` xmeml invariant checks; `nljbs/render_check.py` composites frames from any XML for a visual check
- `episodes/` per-episode edit configs (times are mic-timeline seconds)

Weekly order: `probe` -> `sync --deliver` -> `transcribe` -> `screen` -> write `episodes/R<NN>_edit.yaml` -> `switcher` -> render-check + `lint` -> `switcher --deliver`.
- `legacy/` read-only copies of the R77-R80 scripts from the drive (several hard-code old VM paths under `/mnt/user-data/uploads`)

### Client shorts (`palefire`, Pale Fire and similar clients)

Work files live in `~/r3-work/palefire/<slug>/`. Style rules: `docs/R3_SHORT_FORM_STYLE.md` (read it before cutting).

- `palefire/probe.py` shoot inventory (dedupe, clock fix, scenes, Log detection) -> `shoot.yaml`, contact sheet
- `palefire/transcribe.py` Parakeet per camera clip -> `transcripts/<stem>.words.json` + `.txt`
- `palefire/beats.py` (+ `beats_worker.py`, runs under system `python3.15` or `python3.14`, whichever is installed, with Beat This + torch; `PALEFIRE_BEAT_PYTHON` overrides) -> `music/<track>.beats.json`
- `palefire/cut.py` vertical reels from `shoots/<date>.yaml` (segment kinds talk/punch/action/react/end, beat snapping, take joins, score counter, title card, Montserrat captions, b-roll cutaways over dialogue, `rotate:` for untagged vertical footage, `clip_lut:` per-clip cubes, `{start, end}` hard in/out points) -> XML, SRT, `--preview` MP4
  - Frame checks run before anything is written and stop the build: no shot under 12 frames, no soft or motion-blurred b-roll/action shots, no blurred frames at any shot's edges, speaker's face in frame at both ends of dialogue shots, and word ends measured from the audio (the ASR's end times run short). Never ship a reel that skips them; also eyeball 9 frames around every cut.
- `palefire/music.py` `music index` / `music pick`: the shared music library (folder = tag). Audio lives on the Synology at `/Volumes/2026/R3 MEDIA/MUSIC LIBRARY` (SMB share `2026` over Tailscale; `music/library.yaml` lists where to look). The index (`music/index.json`, `music/beats/`) is in the repo; after adding tracks, run `music index` and commit `music/`. `cut` takes a track name from the library directly.
- `palefire/social.py` `social` (Instagram/Facebook Reels export at -14 LUFS / -1 dBTP + spec and loudness check; takes a shoot plan or finished MP4s like Oz's Premiere exports, which land in `~/r3-work/social/`) and `serve` (Cloudflare quick tunnel so Rella can import; `~/r3-work/bin/cloudflared`)
- `shoots/` per-shoot cut plans with captions and Rella content IDs; `luts/` color cubes (relative `lut:` paths resolve against the repo; `luts/sony/` holds Oz's a7 III S-Log3 LUTs #1 and #2); `scripts/style_measure.py` re-measures the house style (needs the ECC plugin)

Order: `probe` -> `transcribe` + `beats` -> write `shoots/<date>.yaml` -> `cut --preview` -> Avery reviews -> `<id>_FINAL.mp4` -> `social` -> Rella draft as PENDING, `serve`, attach -> the client's reviewer approves; people schedule and turn on auto-publish. Save each reel's caption and Rella content ID in its shoot plan.

## Reading footage cheaply

Every image read stays in context and gets re-sent on each later turn (about 190 times on average before compaction), so read text first and open images second.

- Frames, reels, contact sheets: run `.venv/bin/python scripts/frame_summary.py VIDEO_OR_FRAME_DIR` and read `summary.md` first. It lists luma, sharpness, faces and on-screen text per frame (Apple Vision, local), flags (dark/blown/soft/no-face/dup), and votes on IG handles across frames. Open `sheet.jpg` or `flagged.jpg` only when the text isn't enough, and never more than those two.
- Handles: the vote is a lead. Before a handle goes into public text, confirm it from one tight crop of the screen (a strip, not a full frame).
- Transcripts: run `.venv/bin/python scripts/transcript_outline.py words.json` and read the outline (about 1.2k tokens for 30 min). Use `--find "phrase"` for exact word times. Don't read `words.json` or `transcript.txt` whole.
- Logs: read the last 20 lines of pipeline output or the `_report.txt`, not the full run.
- Source and docs: `grep -n` then `sed -n` the range you need, not `cat` of the whole file.

## Validation

R80 AVE14202: hand-built offset -40.9585 s, `measure()` gives -40.9561 s mid-run, drift 9.6 ms. Re-run this when changing `sync.py`.
