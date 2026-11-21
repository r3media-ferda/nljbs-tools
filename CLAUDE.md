# nljbs-tools

CLI for the NLJBS Shop Talk weekly production run. Full spec: `docs/NLJBS_CLAUDE_CODE_HANDOFF.md` (read it before changing behavior).

## Run

```bash
cd ~/Code/nljbs-tools
.venv/bin/nljbs probe "/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/<date>/RECORDING N"
.venv/bin/nljbs sync ~/nljbs-work/<date>_RECORDINGN/episode.yaml            # build + verify locally
.venv/bin/nljbs sync ~/nljbs-work/<date>_RECORDINGN/episode.yaml --deliver  # also copy XML to the recording folder
```

Python 3.14 venv in `.venv`. ffmpeg/ffprobe come from the `static-ffmpeg` package (no Homebrew on this Mac).
Work files (audio caches, frames, reports, draft XML) live in `~/nljbs-work/<date>_<recording>/`, never on the drive.

## Hard rules

- Never overwrite anything on `/Volumes/NLJBS Drive`. New filenames only; superseded files go to `_to_delete/` for Avery to delete.
- Render to `~/nljbs-work`, then copy to the drive and verify (md5 / byte compare).
- Heavy ffmpeg jobs run one at a time in the foreground.
- Never name a module `xml.py`.
- Artist handles come from the screen (OBS IG header) or transcript, never from memory.
- Public text (titles, captions, descriptions) in NLJBS voice: casual, shop-floor. Never the word "swag".
- Publishing is outward-facing: dry run first, Avery confirms before any real upload.

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
- `palefire/beats.py` (+ `beats_worker.py`, runs under system `python3.14` with Beat This + torch) -> `music/<track>.beats.json`
- `palefire/cut.py` vertical reels from `shoots/<date>.yaml` (segment kinds talk/punch/action/react/end, beat snapping, take joins, score counter, title card, Montserrat captions, b-roll cutaways over dialogue, `rotate:` for untagged vertical footage, `clip_lut:` per-clip cubes, `{start, end}` hard in/out points) -> XML, SRT, `--preview` MP4
  - Frame checks run before anything is written and stop the build: no shot under 12 frames, no soft or motion-blurred b-roll/action shots, no blurred frames at any shot's edges, speaker's face in frame at both ends of dialogue shots, and word ends measured from the audio (the ASR's end times run short). Never ship a reel that skips them; also eyeball 9 frames around every cut.
- `palefire/music.py` `music index` / `music pick`: the shared music library (folder = tag), analyzed into `~/r3-work/music/`; `cut` takes a track name from it directly
- `palefire/social.py` `social` (Instagram/Facebook Reels export + spec check) and `serve` (Cloudflare quick tunnel so Rella can import; `~/r3-work/bin/cloudflared`)
- `shoots/` per-shoot cut plans with captions and Rella content IDs; `luts/` color cubes (relative `lut:` paths resolve against the repo); `scripts/style_measure.py` re-measures the house style (needs the ECC plugin)

Order: `probe` -> `transcribe` + `beats` -> write `shoots/<date>.yaml` -> `cut --preview` -> Avery reviews -> `<id>_FINAL.mp4` -> `social` -> Rella draft, `serve`, attach -> Avery schedules and turns on auto-publish.

## Validation

R80 AVE14202: hand-built offset -40.9585 s, `measure()` gives -40.9561 s mid-run, drift 9.6 ms. Re-run this when changing `sync.py`.
