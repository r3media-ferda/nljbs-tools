# NLJBS Shop Talk — Claude Code Handoff

You're Claude Code running on Avery's Mac. Your job: turn the weekly NLJBS production run (sync → edit build → packaging → reels → publishing) into repeatable scripts Avery can fire with one command. Everything below was learned over ~11 releases (R70–R80) of doing this by hand with Claude in the claude.ai app. Treat it as the spec.

Compiled 2026-11-17 from the NLJBS PODCAST project docs, project memory, and the original project chats.

---

## 0. Read this first

- **Avery runs the commands.** Be direct. Exact commands, exact paths, no preamble. Context arrives as screenshots and file paths. Deliver the artifact (the XML, the CSV, the description), not a plan for building one.
- **Never overwrite files on the NLJBS Drive.** Write new filenames / new folders. Superseded files go into a `_to_delete/` subfolder; Avery deletes them.
- **Render locally, then copy.** ffmpeg writing an mp4 straight onto the NLJBS Drive has produced corrupt files (no moov atom). Render to a local work dir, `cp` to the drive, then `md5` both. Re-run the md5 a moment later if it says "No such file" right after the copy.
- **Run heavy ffmpeg jobs one at a time in the foreground.** A 9–18 GB camera file's audio pulls in ~5–45 s that way.
- **Don't name a script `xml.py`** (shadows Python's `xml` package).
- **Never take artist handles or names from memory.** Read them off the IG post header in the OBS screen recording or from the transcript. Credit the artist, not the shop account that reposted it.
- **Tone for anything public-facing (titles, captions, descriptions):** NLJBS voice — casual, edgy, shop-floor, unfiltered. Never R3 Media's polished voice. Never the word "swag."

### What's different now that you run natively on the Mac

The earlier work ran through a sandboxed Linux VM shell that mounted the drive. Several "quirks" in the build notes were VM-only and should not apply to you:

| Old VM problem | Native Claude Code |
|---|---|
| Drive mount dropped mid-session, fixed by quitting the Claude app | Gone. You see `/Volumes/NLJBS Drive` directly. |
| `/tmp` wiped on restart, `/sessions` home ~1 GB | Use a persistent work dir, e.g. `~/nljbs-work/`. |
| Hugging Face / OpenAI model hosts blocked → no Whisper | Probably reachable now. Parakeet still works and is proven; Whisper (e.g. `mlx-whisper` on Apple Silicon) is an option. |
| api.opus.pro not reachable | Probably reachable now. |
| YouTube API not reachable → Avery ran uploads in Terminal | You can run the uploaders yourself (Avery still confirms the channel prompt). |
| No scipy | Install what you need in a venv. |

The drive-overwrite and mp4-corruption problems may have been the drive (exFAT/USB) rather than the VM. Keep the render-locally-then-copy rule until proven otherwise.

**Python:** the Mac's system Python 3.9 / LibreSSL 2.8.3 kept dropping long Google uploads. Avery installed **Python 3.14** from python.org (`python3.14`). Use that, in a venv.

---

## 1. The show and the people

- **NLJBS** = *No Lies Just Bullshit*, a tattoo-culture YouTube channel centered on **Alley Cat Tattoo**, Harrisonburg, VA. Handle `@noliesjustbullshit`, site noliesjustbullshit.com.
- **Shop Talk** is the multicam podcast, shot in the shop. They pull up tattoo artists' Instagram posts on a browser (captured by OBS) and break the pieces down. **The point of the show is to highlight the tattoos and the artists' IG handles.**
- **NLJBS Chronicles** is the second series. Same title rules. No build history yet.
- **Shenandoah Rose** (Aug 7–9, Alley Cat Tattoo's 25th anniversary) is a recurring promo element; its footage is in the intro b-roll.

| Person | Role | Handle |
|---|---|---|
| **Avery Leavitt** | Producer/editor (Ave Leav Photo / R3 Media). Edits in Premiere, posts to YouTube. Time zone America/New_York. | — |
| **Nick (Nick Swartz)** | Host ("Nikki James" / "fearless leader"), usually on mic 1. Runs NLJBS Instagram + Facebook (Avery doesn't). Payee on the AdSense account. **Has veto on content**: R79 he had the stripper story and a false Mike Rubendall story cut after seeing the reels. | — |
| **Andrew Conner (AC)** | Regular co-host/guest. Spelled **Conner**. Mic is quiet relative to others. | `@aeconner` |
| **Porter (Chris Porter)** | Regular co-host; hosted R79/R80 when Nick was out. | `@porter_electric` |
| **Jake Hawk** | Alley Cat artist, third person on the couch in R80. Spoken "Jake Hawk", tagged **@jake_hock**. | `@jake_hock` |
| Dan | Collaborator; hosts the Synology NAS for now. | — |
| Oslyn | R3 Media co-founder (not NLJBS). | — |

Who's on which mic and which camera **changes every episode**. Always verify from frames and from each person saying their own handle in the outro.

---

## 2. Drives, folders, naming

Verify on disk before relying on any of these; they come from build notes.

```
/Volumes/NLJBS Drive/
├── WORKING SHOP TALM FILES/          ← yes, "TALM" (typo is the real name)
│   ├── 10.05.26/                     ← one folder per recording date (MM.DD.YY)
│   │   ├── Release 76/ Release 77/ Release 78/   ← older layout: one folder per release
│   │   └── release 77/_claude_work/scripts/ ...
│   ├── 10.26.26/
│   │   ├── RECORDING 1/              ← newer layout: one folder per recording = one release (R79)
│   │   ├── RECORDING 2/              ← R80
│   │   └── _claude_work/            ← scripts + data (r80/, reels79/, scripts/ …)
│   └── _youtube/                     ← publishing scripts + Google OAuth
│       ├── post_shorts.py / post_shorts_v2.py   (v2 = chunked + retry; use v2)
│       ├── upload_episode.py
│       ├── send_to_drive.py / send_to_drive_v2.py
│       ├── client_secret.json        ← Google OAuth desktop client ("NLJBS Uploader" GCP project)
│       └── token.json                ← saved login
├── canon-lut-202510/                 ← Canon C-Log3 LUT .cube files
├── VIDEOS FOR TRAINING/              ← Avery's finished edits as XML (R70, R76) used to learn the style
├── OPUS CLIPS/_assets/               ← R77 reel scripts, Anton-Regular.ttf, align_clip2.py, make_reels.py
└── NLJBS/PODCAST VIDEO B-ROLL/       ← intro b-roll
/Volumes/This PC/                     ← intro music: SHOP TALK SCRATCH.wav, SHOP TALK BEAT.wav
/Volumes/Premiere Pro/                ← Avery's final exports, e.g. "Release 79.mp4"
```

Inside a recording folder you'll typically find:

- **Cameras:** `AVE#####.MP4` and `093A####.MP4` (Canon, C-Log3, HEVC 4:2:2 10-bit), `C00##.MP4` (Sony wide, 119.88p, 8-bit H.264 full-range, untagged; earlier episodes PCM audio).
- **OBS screen recording:** `YYYY-MM-DD HH-MM-SS.mp4` (60 fps, yuv420p bt709), captures the browser plus a mix of the mic feed.
- **Mics, two possible forms:**
  - **GarageBand exports** (preferred): e.g. `mic 1.wav`, `MIC 2 - AC.wav`. 44.1 kHz 16-bit **dual-mono (L = R)** → use channel 1 only.
  - **Raw recorder takes** inside `<name>.band/Media/Audio Files/`: `Mic 1#54.wav` (mono 24-bit 44.1k). A .band can hold several takes (#52 R1, #53 false start, #54 R2 …) — pick by length/date. `Left/Right Audio Channel` files are the recorder's sum: ignore.
  - **Rule (R80): always build on GarageBand exports, never the raw .band files.** Raw files on stereo-pair tracks played silent in Premiere. GarageBand exports start from the GarageBand project start, so they carry an offset vs the raw takes (R80: raw t=0 at 68.5026 s into every export). Measure it.

**Output naming (keep it):**

```
ShopTalk_<MM-DD-YY>_R<NN>_SYNCED.xml
ShopTalk_<MM-DD-YY>_R<NN>_SWITCHER.xml
ShopTalk_<MM-DD-YY>_R<NN>_<VARIANT>.xml      (REMAKE, COLD_OPEN, RECUT_A_<slug>, FINAL_ONEMASTER …)
R<NN>_THUMBNAIL.png
R<NN>_DESCRIPTION.txt / R<NN>_YT_DESCRIPTION_FINAL.txt
R<NN>_PLATES/            (backdrop, white/black, card_<handle>.png, holds/ hold_S1_0608.95.png — named by time)
R<NN>_REELS/R<NN>_<NN>_<slug or handle>.mp4
R<NN>_REELS/R<NN>_CAPTIONS.txt
R<NN>_REELS/R<NN>_SHORTS_SCHEDULE.csv
```

Episode number = last release + 1. Say which number you used.

Other storage: Synology DS925+ NAS (2× IronWolf 10 TB RAID 1) over Tailscale, at Dan's for now. SanDisk 2 TB SSD (active), Seagate Expansion 8 TB (SMR, slow writes).

---

## 3. The weekly deliverable set

Avery drops a recording folder and says "do Shop Talk." In order:

1. **`_SYNCED.xml`**: plain multicam sync. Deliver first, it unblocks Avery.
2. **Transcript + episode map**: word timestamps, speaker per word, sections (pre-show, banter, each artist/post with OBS times, outro, post-show).
3. **Titles** (4–5 ranked) + **thumbnail** + **description** with chapters.
4. **`_SWITCHER.xml`**: the full auto edit (10 angle nests, handle cards, intro package, hype trailer/cold open at the head).
5. Avery edits in Premiere → exports his XML → **diff/fix pass** (carry his edits forward, fix track bumps, color/master-clip problems).
6. **Reels** (5–7) + `R<NN>_CAPTIONS.txt` + `R<NN>_SHORTS_SCHEDULE.csv`. If Avery's final-cut XML exists, diff it first and keep reels off anything he cut.
7. **Final description with chapters matched to the actual exported mp4** (audio-match the export against the mics).
8. **Publish:** long-form via `upload_episode.py` (scheduled, usually 9 PM ET), Shorts via `post_shorts_v2.py` (one a day at 18:00), reels + captions into Nick's Google Drive folder via `send_to_drive_v2.py`.
9. **Build notes**: write `shop-talk-r<NN>-build.md` (offsets, roles, sections, what changed, new quirks).

Downstream chain in Premiere: **GarageBand WAV export → Premiere sync → Essential Sound → FireCut** (FireCut does an automated cutting pass and needs the 29.97 sequence).

---

## 4. Multicam sync — exact method

### Why envelopes
Cameras record the **room** (reverb, off-axis voices, HVAC). Clean mic WAVs come off **one recorder**, sample-locked to each other. Raw-waveform cross-correlation between a camera and a lav fails. The **speech-energy envelope** survives the room; the waveform doesn't.

### Steps
1. **Extract** every mic and every camera/OBS audio to **8 kHz mono raw** with ffmpeg, one at a time, foreground:
   `ffmpeg -v error -i IN -map 0:a:0 -ac 1 -ar 8000 -f f32le OUT.f32`
2. **Reference = mix of all mic tracks** (sum, normalize). Check peaks for clipping.
3. **Envelope:** RMS (or abs + low-pass) of the band-limited signal per hop. Log-compress, subtract the mean.
4. **Coarse match:** 10 ms hop, cross-correlate camera envelope vs mic-mix envelope over the full length (FFT). Confidence = peak / median of |xcorr|. Good matches landed at 190–400; treat < ~50 as suspect.
5. **Fine match:** 1 ms hop, ±50 ms around the coarse lag.
6. **Drift check:** 5 windows of 90 s (or head/mid/tail 120 s) at 0.5 ms hop, ±100 ms around the expected offset. A window in pre-show silence will show low confidence: ignore it. Observed drift has always been ≤ ~14 ms over 20 min, so **one constant offset per camera** (use mid-run value) has always been correct.
7. **Place each video relative to the mics**, rounding the mic↔video offset to whole frames at 29.97, so the error that matters (lip sync vs clean audio) is minimized. Report the per-clip rounding residual (has been ≤ 8–20 ms).
8. **Re-measure from the written XML** at 3 points. Residual must be ≤ ~10–20 ms.
9. **Probe every source with ffprobe** in this step (fps, codec, pix_fmt, color tags, duration) and flag anything unusual before building.

The earliest-starting source goes at frame 0. Negative offset = that source rolled before the mics.

### Fallback: mic WAVs missing or corrupt
Use the **OBS screen recording** as the audio reference (it captures the mic feed). Same method. Caveats: it's a single stereo mix (L/R corr ~0.97), so no per-speaker Essential Sound work; check for clipping; verify no drift. Used in R72 and R77. In that case speaker ID can come from the **stereo pan** of the screen-rec mix (R77: Nick centered L−R ≈ 0.2 dB; L−R < 0.7 dB = Nick).

### Reference offsets from past episodes (sanity check your numbers)

| Release | Reference | Offsets (s, vs reference start) |
|---|---|---|
| R72 08.31.25 | screen rec | C0012 −45.536 · 093A9480 −28.634 · AVE13396 −15.029 |
| R74 09.07.26 | mics | 093A0530 −10.252 · AVE16598 −15.123 · OBS +48.353 |
| R76 10.05.26 | mics | AVE11877 −4.091 · C0001 +7.232 · 093A2067 +20.566 · OBS +30.624 |
| R77 10.05.26 | screen rec | C0003 +36.331 · 093A2068 +56.070 · AVE11878 +81.611 |
| R78 10.05.26 | mics | AVE11879 −10.170 · 093A2069 −36.675 · C0004 +4.008 · OBS +17.701 |
| R79 10.26.26 | mics | AVE14201 +8.233 · 093A6723 +4.234 · C0011 +15.522 · OBS −1.505 |
| R80 10.26.26 | mics (raw) | AVE14202 −40.9585 · 093A6724 −61.856 · C0012 −81.128 · OBS −64.4875 |

---

## 5. FCP7 XML (xmeml) spec — what Premiere actually needs

- `<xmeml version="4">`, sequence **29.97 fps**: `<rate><timebase>30</timebase><ntsc>TRUE</ntsc></rate>` on the sequence and on every clipitem/file. Getting this wrong throws every offset. Timecode display NDF is fine.
- Sources with other frame rates (119.88p Sony, 60p OBS) still get `timebase 30 / ntsc TRUE` in/out values in **sequence frames**; Premiere conforms. Convert in/outs exactly when re-pointing.
- **`pathurl`**: `file://localhost/Volumes/NLJBS%20Drive/...` — URL-encode spaces (`%20`) and **`#` as `%23`** (raw mic names like `Mic 1#55.wav`).
- **`pproTicksIn` / `pproTicksOut`**: Premiere reads these **instead of** `<in>`/`<out>` when present. 254016000000 ticks per second. **Any time you change a clip's in/out, update its pproTicks too** (R78 cold-open v1 was completely out of sync because of this). Simplest: strip them from generated clips, or always recompute.
- **HARD RULE (R80): every camera and OBS `clipitem <name>` must equal its source file name** (`093A6724.MP4`, not "SPLIT CAM" / "PIP CAM" / "IG POST"). Premiere 2026 imports each differently named clipitem as a separate master clip even with the same file id/masterclipid, so a master-clip Lumetri/LUT lands on one copy and not the others → color jumps between angles. Name nests and tracks descriptively; leave clip names alone. Cards/plates/mics can keep descriptive names.
- **Mics on mono tracks** (one track per mic), channel 1 of dual-mono exports. Don't put mono raw files on stereo-pair ("exploded") tracks.
- **Camera scratch audio** on separate tracks, **disabled** (reference only).
- **Track order:** Avery wants the **AVE camera on V1** in the plain sync XML.
- **Intro music:** exactly **one stereo pair for SCRATCH and one for BEAT** (R80: BEAT at 0.708, SCRATCH at 0.561). The R78 template copied in 16 audio tracks that were "super loud" — never again.
- **No Lumetri carried over from old XMLs.** LUTs live on source master clips in Avery's project (see §7). Old R76 Lumetri had an empty LUT slot + manual tweaks that look awful on raw log.
- **Essential Graphics text** (episode number, handles) is a binary blob inside the XML. Patching works if you update the uint32 length prefix and stay within the padded slot (R80: `@aeconner` → `@jake_hock`, length 9→10 at offset 356, string at 360). Copy the graphic from the last finished edit and patch.
- Import translation report always flags the two music volume effects and the "Inset" transition → Cross Dissolve. Harmless.
- **After Avery edits, check that V1 still holds ANG 1 at the end of the timeline.** Ripple cuts in his edits have bumped the whole angle stack up one track from the cut onward (R78 at 10:38 and again at 11:04). Fix = move every item after the cut down one track.
- **Check renders:** `render_check.py` renders frames from any XML via ffmpeg. For JPG/PNG stills don't pass `-ss` (ffmpeg returns nothing). Look at the frames before delivering.

---

## 6. The switcher edit (what the auto build does)

Learned by diffing Avery's finished edits (R70, R76, R77, R78, R79, R80) against the raws.

### Structure
- **Hype trailer / cold open: 25–30 s at the head**, before the intro. It pays off **the title and thumbnail** (that's what people clicked). One thread: stakes → payoff → open loop, cutting into the intro on an unfinished line. If the title names a tattoo, it's on screen in the first 15 s. Re-ASR the trailer audio to confirm clean word boundaries. Why: R76/R77 lost 38% of viewers by 0:28 and retention *rose* when the promised tattoo finally appeared minutes in (people scrubbing).
- **Intro package: 400 frames (13.3 s)**, same every episode. Copy it from the last finished edit and swap `ep:NN`. Music `SHOP TALK SCRATCH.wav` + `SHOP TALK BEAT.wav`, b-roll montage at 54–65% scale, "Welcome / to / shop / shop talk" text, SHOP TALK title + `ep:NN`, NLJBS graphic, Dip to Color + Inset at 00;00;10;04.
- **Body** after the intro. `Untitled_Artwork.heic` is the split-screen backdrop (later builds use a blurred wide still).
- **Pre-show** is cut from the body (29–100 s; R79's was 4:20, and they said on mic "none of this goes into this"). Respect anything said like that. The opening banter is still gold for funny reels ("the bullshit in the beginning is always funny").
- **Outro: last ~2.5 min on cameras only** (host full / two-shot / wide; no splits, no tights). Handle card ends where the outro starts. Shout-out graphics for `@aeconner`, `@porter_electric` (and guests like `@jake_hock`) in **BlackTakora-Regular** on a top track, timed to when they say it. Post-show is dropped.
- **Content cuts:** 8–14 internal cuts, 9–14% of raw; dead air ≥ 2 s tightened to ~0.9 s. Avery's own passes trim more (stumbles, off-topic, anything Nick vetoes). No bleeps (Avery handles those).
- Finished runtimes: 17–25 min.

### The 10 angle nests (main timeline V1–V10, only the chosen one enabled; swap with Shift+E)
R77/R78 (Nick + two guests): 1 NICK · 2 GUESTS (two-shot) · 3 WIDE · 4 SPLIT NICK+TATTOO · 5 SPLIT GUESTS+TATTOO · 6 TATTOO+NICK PIP · 7 TATTOO+GUESTS PIP · 8 TATTOO ONLY · 9 NICK TIGHT · 10 GUESTS TIGHT.
R80 (Porter / AC / Jake): 1 AC+JAKE · 2 PORTER · 3 WIDE · 4 SPLIT AC+JAKE+TATTOO · 5 SPLIT PORTER+TATTOO · 6 SPLIT WIDE+TATTOO · 7 TATTOO+WIDE PIP · 8 TATTOO ONLY · 9 AC TIGHT (AVE crop 175%) · 10 JAKE TIGHT (AVE crop 190%).
V11 = all 10 angles as a multicam source, **disabled**. It pushed Premiere to 38.75 GB RAM in R80; make it optional/off by default. V12 = handle cards.

The angle set must be generated **from a per-episode cast config** (who's on which mic and camera), not hard-coded.

### Speaker switching (from the clean mics)
- 50 ms RMS band levels, 150–3500 Hz.
- 3 mics: a frame belongs to the loudest mic when it leads by > 4 dB and sits above an activity floor (−47 dBFS or the 35th-pct level); else inherit. 1.2 s majority vote; runs < 2.6 s merged. Bleed is 5–13 dB down. Matched the talking mic on ~83% of speech frames.
- 2 mics with a quiet AC (R79): d = mic2 − mic1; AC if d > −4, Porter if d < −8, else inherit.
- Speaker-follow: host → host single; guests → two-shot. Wide/reaction insert on runs > 8–12 s. Punch-ins rare: every 6th–7th shot, only on 4–9 s shots (Avery pulled tights back every time).
- Shot length: median 4.2–6 s.

### Screen-share layouts (40–84% of runtime)
- Detect screen states from the OBS rec (2–10 fps frame-diff + image-box detection, `boxdet2.py`). Per-state crop boxes, fixed panel aspect per artist section so the panel never jumps size.
- **Splits dominate** in Avery's edits (~78% of screen time). Tattoo-only is short beats and **centered** (panel x = 960 ± PW/2, handle card slides with it). PiP layouts basically never.
- **Never drop to camera on scrolls/swipes/loading/pop-ups.** Hold a still of the last stable frame (`holds/`) in the same panel geometry. Sustained motion ≥ 3 s inside a carousel = tattoo video, play it live.
- Split panel: post panel right-aligned at x1880, y180–1050 (870 tall); camera box left, vertically centered.
- **Handle card (Avery's rule): always on screen whenever IG content is up, top RIGHT directly above the tattoo panel**, one fixed spot, never over the post. It's a screenshot of IG's own post header (avatar + handle + subline) at 1.7×, on #1C2225 with a 6 px white border, full-frame PNG with alpha, right edge x1880, y36–163. If there's no IG header (Photos app), typed "@handle" in Liberation Sans Bold on the same card. Sits on V12 for the whole artist segment across all angles. If the header can't be read, hold the last good card.
- Capture-side tip for Avery: lock browser window size and zoom every episode (zoom changes broke fixed crops repeatedly).

### Angle balance from Avery's final edits (target this)
R78 build → his edit: split guests 381 → 432 s · split Nick 248 → 240 · Nick 238 → 251 · two-shot 100 → 152 · wide 104 → 116 · tattoo-only 127 → 19 · tights 71 → 44 · PiP 0. Talk sections: less host, more wide and two-shot.

### Carry-over of Avery's edits
Avery exports his sequence as FCP XML → diff by nest in-point (source frame) → map his enabled angles and deletions → lay them over a new build (`diff_user.py`, `build_switcher_v4.py`, `diff_r78_edit.py`, `remake80.py`). `remake80.py IN OUT X1 X2 X3 SR CH` re-points mic clips at new exports while keeping every video edit.

---

## 7. Color

- **093A camera** (two-shot / Porter in R79–R80): C-Log3 / Cinema Gamut → Canon `CinemaGamut_CanonLog3-to-BT2020_709WideDR_65_FF` (or CinemaGamut CanonLog3 → BT.709) LUT.
- **AVE camera** (Nick single / AC): C-Log3 / BT.709 gamut → Canon `BT709_CanonLog3-to-BT709_WideDR_65_FF` LUT (+ Avery's sat/contrast tweaks).
- **Sony wide C00xx:** manual grade, no LUT. Not log/HLG.
- LUTs in `/Volumes/NLJBS Drive/canon-lut-202510/`.
- Apply as a **master clip effect** (Lumetri → Input LUT on the *Source* tab, not the sequence tab; Premiere flips back to the sequence tab when you click a timeline clip — that's how a LUT ended up on one nest's clip in R80).
- **Premiere 2026** auto-detects Canon Log inside sequences. Avery's setup: auto-detect log **off**, Interpret Footage Rec.709 on AVE/093A/C0012, LUTs only on source master clips. Nest vs main-sequence Color Management settings must match (Direct Rec.709 SDR).
- For reels/thumbnails rendered with ffmpeg: use the .cube LUTs via `lut3d`. Fallback eq strings: AVE `eq=contrast=1.22:brightness=0.05:gamma=1.22:saturation=1.4`; 093A `eq=contrast=1.32:brightness=0.03:gamma=1.38:saturation=1.38`. Reels want a warm, bright, saturated grade.

---

## 8. Transcript, speaker ID, word timing

- **Proven offline ASR:** sherpa-onnx (pip) + NeMo **Parakeet TDT 0.6B v2 int8** from `k2-fsa/sherpa-onnx` GitHub releases (`asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2`). ~1.3 min for a 29-min mic mix on 4 cores. Chunk at quiet points every 18–28 s. Tokens start with a plain space (not '▁'): split words on that. Word end = min(next onset − 0.02, onset + 0.10 + 0.07·len).
- Keep a **FIX map** for names/handles the ASR mangles ("Maddie Damuni" = @matty_d_mooney, "AE Connor" = @aeconner, "Jake Hawk" = @jake_hock).
- Premiere's transcript export came back as one untimed block. If you need Premiere's text, ask for an **SRT/captions export** (timed).
- Speaker per word: loudest mic inside the word (50 ms band level), must lead by > 5 dB, else inherit; 1-word islands absorbed; turns < 0.6 s fold. 2-mic quiet-AC variant: d = mic2 − mic1 over [onset+20 ms, min(next onset, onset+450 ms)]; AC if d > +1.5, Porter if d < −9.
- Silence trim only between words: the quiet run must end at a word onset, contain no onset, and start ≥ 0.35 s after the previous onset (energy-only trims chopped words). Cut gaps > 0.30 s, keep 0.08 s padding.
- **Final-cut ↔ source time:** for chapters and reels after Avery's edit, audio-match his exported mp4 (or XML) against the mic mix in 1 s windows (monotonic offset map; R80 corr 0.95+). His content cuts shift everything after them.

---

## 9. Titles, thumbnails, descriptions

### Titles
- Format: `Shop Talk NN | [hook]` (number included since R78) or `NLJBS Chronicles | [hook]`.
- Hooks come from **the actual transcript**, not a topic summary. Pull the moment that carries tension.
- Judge every option on **stakes, curiosity gap, click psychology**. Lead with tension or payoff, never a neutral description.
- Deliver **4–5 options ranked, one-line reason each**.
- **Channel data (Studio CTR, Oct 2026):** titles that promise a tattoo get **6–8% CTR** (Most Important Line 7.7%, Best Back Piece 7.2%, Anti Ink Master 7.3%, 3 Insane Tattoos 6.3%). Banter/joke titles get 3.5–5% (Bag of Eels 3.5%, 1 Star 4.7%, Wolf 5.2%). Old numbered podcast eps 1.3–3%. vidIQ's title score disagreed (scored banter 99) — trust the channel's CTR. Title, thumbnail, and cold open must sell the **same** promise.
- Recent picks: R79 "Shop Talk 79 | Nick's Out. Seventh Son's Dragon Backpiece Takes Over"; R80 "Shop Talk 80 | An Ink Master Champ's Tiger Backpiece" (Avery picked the credential/tattoo option over "You Ain't Never Seen That Before").
- vidIQ handles back-end metadata (tags, keywords). Claude does titles, hooks, descriptions.

### Thumbnail (1280×720)
Built from real frames: host/guest faces (most animated moments, pick by loudness) + tattoo card with white border tilted right + the real IG header card under it + red SHOP TALK tag + **short** 2-line hook (white + yellow) bottom left. HTML with Anton (`@fontsource/anton`) rendered via Playwright. Avery's R80 notes: **better color on guest faces, and keep the text short so it's not in the way.** No nudity (R79 dragon cropped to upper back). Grab frames from the **final export** so faces carry Avery's grade.

### Description — short and raw
Long descriptions with emojis, taglines, and hashtag walls are "super corny" and not NLJBS. Template (R79 final):

```
Nick's out, so Porter and AC run the shop. A moth hand blast that sits right over the bone and still holds, a Seventh Son dragon backpiece done corner to corner, and the paintings hanging on the shop wall.

Artists in this episode:
@cum_eels (Kings Avenue Tattoo NYC)
@smithtattoosf (Seventh Son Tattoo)

0:00 No Nick
0:24 Shop Talk
0:37 Nick's out, Porter and AC run it
1:03 @cum_eels - moth hand blast
3:45 @smithtattoosf - dragon backpiece, corner to corner
8:15 The paintings on the shop wall
12:48 Outro

Shop Talk with Porter (@porter_electric) and Andrew Conner (@aeconner) at Alley Cat Tattoo, Harrisonburg VA.
@noliesjustbullshit
```

Chapters: first at 0:00, each ≥ 10 s (YouTube drops shorter ones; merge), times from the **actual exported file**. One chapter per artist named by handle — chapters turn scrubbing into navigation and make the episode searchable by artist.

Also recommended (from the Oct growth audit): end screen over the outro pointing to the previous episode / Shop Talk playlist; post every episode's reels as Shorts linked to the episode.

---

## 10. Reels / Shorts (R78 v3 format is locked)

Avery: "I liked how we ended last week's style." Built from raw footage, not Opus (R77 Opus reels underperformed).

**Content**
- 5–7 per episode: **1–2 per artist's tattoo** + **1–2 funny** (pre-show banter is fair game even when cut from the episode).
- Each artist's reel is about **that artist's tattoo only.** General talk doesn't go over another artist's work with their handle. **Never put a negative story ("he fucked it") over a credited artist's work.**
- Strong themes get their own reel (e.g. "black and gray holds/heals").
- Many are IG collab posts with the artist, so **say the artist's name in the audio** when possible.
- Respect Nick's vetoes (R79: stripper + false Rubendall reels pulled from posting and Nick's Drive).

**Format (1080×1920)**
- 13–57 s, sweet spot ~26–45 s. **Cold open on the punchline.** Something visibly changes in the first ~1 s (cut or punch-in; tattoo doesn't have to be first).
- **Full-frame shots, not panels:** speaker tight (face upper third) OR tattoo full-bleed. Cut every 2–3.5 s alternating speaker ↔ tattoo. Face on screen = **whoever is talking**, cut on the speaker change, no reaction cutaways.
- **Slow zooms stay:** 5% push inside every face shot; tattoo shots are continuous OBS video with a 1.8%/s push that carries across returns to the same tattoo (cap 1.16), 6-frame dissolves on every tattoo boundary. Tattoo fit inside 1080×1300 centered at y880 over its own blurred fill. Per-reel `clamp=(obs_start, obs_end)` so a tattoo shot never drifts onto the artist's next post. Wide boxes (> 1.15:1) centre-crop to 0.95:1. If the screen shows a process clip, pull from a pool of finished-piece windows.
- **Faces: detect per shot** with YuNet (`opencv_zoo` `face_detection_yunet_2023mar.onnx`; download from media.githubusercontent.com, the github.com URL is an LFS pointer). Two people on one camera: pick by side.
- **Captions on the word:** BlackTakora-Regular (file from Avery), 1–3 words per card, white with **red** keywords, centered at ~61–70% of frame height (on the chest, never a face).
- **@HANDLE** in white blackletter at the top, only over tattoo shots.
- No dead air. Audio = clean mic mix, measured with ebur128 → gain + alimiter to **−14.0 LUFS, TP ≤ −1.4 dBTP**.
- Safe zones (IG/FB Reels): top ~270 px and bottom ~670 px covered by UI, right ~230 px buttons. Faces and captions live in y ≈ 270–1250.
- Not built yet: a framed card look (tattoo-flash pattern bands top/bottom + "noliesjustbullshit" across the top). Needs the pattern image from Avery.

**Pipeline (R80):** `specs80.py` (ranges by phrase: approx time + first word / last word; resolver snaps to ASR words) → `plan80r.py` → `ass80.py` → `render80.py` (`--mux` to re-burn captions only) → `verify80.py`. ~40–70 s per reel. Every render from ONE input with setpts reset (fixes flash frames).

**Verify every reel before handing over:** re-ASR rendered audio vs caption cards (median ≤ 0.05 s, p90 ≤ 0.12 s), per-frame luma-dip scan, loudness, 1 fps contact sheet for face/speaker/tattoo — and actually look at the sheets (that's how the R80 wrong-post and letterbox bugs were caught).

**Downloads per episode**
- `R<NN>_CAPTIONS.txt`: per reel title / caption / hashtags / collab handle + suggested post order.
- `R<NN>_SHORTS_SCHEDULE.csv`: `file,title,description,tags,publish_local`. One Short a day at 18:00 ET, starting the day after the last scheduled one. Description ends "Full episode on the NLJBS channel."

---

## 11. Publishing

All in `WORKING SHOP TALM FILES/_youtube/`, Google Cloud project **"NLJBS Uploader"** (YouTube Data API v3 + Google Drive API enabled, OAuth consent External/testing, Avery's accounts as test users, Desktop-app client in `client_secret.json`, login cached in `token.json`).

```bash
cd "/Volumes/NLJBS Drive/WORKING SHOP TALM FILES/_youtube"

# Shorts: dry run, then real (confirms channel name, type y)
python3.14 post_shorts_v2.py "../10.26.26/RECORDING 1/R79_REELS/R79_SHORTS_SCHEDULE.csv" --dry
python3.14 post_shorts_v2.py "../10.26.26/RECORDING 1/R79_REELS/R79_SHORTS_SCHEDULE.csv"

# Long-form: uploads private, scheduled public
python3.14 upload_episode.py "/Volumes/Premiere Pro/Release 79.mp4" \
  --title "Shop Talk 79 | ..." --desc "../10.26.26/RECORDING 1/R79_YT_DESCRIPTION_FINAL.txt" \
  --thumb "../10.26.26/RECORDING 1/R79_THUMBNAIL.png" \
  --tags "shop talk|nljbs|tattoo podcast|alley cat tattoo|..." --when "2026-11-04 21:00"

# Reels + captions into Nick's Drive folder
python3.14 send_to_drive_v2.py "../10.26.26/RECORDING 1/R79_REELS" --into-id <folder id>
```

- Scripts won't schedule anything < 15 min out. When two batches overlap, the older batch went at noon, the new one at 18:00.
- **Nick's Drive folder:** on the **aveleavphoto** Google account (not the VVP Workspace account): `SHOP TALK › Instagram Content › <Month> › <date folder>` (e.g. `November › Nov 3`, `October › October 28th`). Nick has edit access and posts to IG/FB from there.
- If Google says "app isn't verified": Advanced → Go to NLJBS Uploader. SSL/connection drops = old Python; use 3.14. `CERTIFICATE_VERIFY_FAILED` → `open "/Applications/Python 3.14/Install Certificates.command"`.
- Long-form usually goes public **9 PM ET**.
- Publishing is outward-facing and can't be undone cleanly: **always dry-run and get Avery's go before a real upload.**

---

## 12. Opus Clip

- Opus was used for short-form before R78; Avery now prefers our own reels, but it's still in the toolbox.
- **If Opus breaks, don't grind.** Once browser, cache, VPN, and hotspot are ruled out, it's platform-side: file a support ticket.
- API (checked 2026-10-20): Pro (Beta)/Max/Business. Org API key under "API Access" in the dashboard. 1 credit = 1 min, 10-credit min per project, 15 h/month on Pro Beta/Max, 30 req/min, 4 parallel projects. Docs: help.opus.pro/api-reference. Rejects Google Drive links: upload via upload-links → GCS resumable PUT → clip-projects with `videoUrl = uploadId`. Key + org stored in macOS Keychain as `opus_api` / `opus_org`; script `opus_clips.sh`. PRO renders full 1080×1920 only for the top ~14 clips.
- Opus clip polish recipe (vidIQ notes): cold open on the punchline, punch-ins 1.12–1.16 with 5-frame ease, cover Opus captions with a blurred band and burn our own.

---

## 13. Known pitfalls (the full list)

1. Raw-waveform sync fails — envelopes only.
2. Wrong sequence fps (anything but 29.97 NTSC) throws every offset.
3. `pproTicksIn/Out` not updated → Premiere ignores your `<in>/<out>`; audio wildly out of sync.
4. Clipitem names ≠ source file name → separate master clips → LUT/color jumps between angles.
5. Raw .band mic files on stereo-pair tracks → silent in Premiere. Use GarageBand exports on mono tracks; measure the export offset.
6. Copying the R78 intro template's 16 audio tracks → stacked, way too loud. One stereo pair per music file.
7. Ripple cuts in Avery's edit bump the angle stack up one track. Check V1 = ANG 1 at the end.
8. Premiere memory blowup (38.75 GB) from the V11 multicam stack + many open sequences → software-render fallback, inconsistent color. Make V11 optional; Avery's baseline is V11 deleted, one tab open, 1/4 playback.
9. Premiere 2026 auto log detection + nest/main color-management mismatch → double conversion ("fried" tattoos).
10. Lumetri LUT landing on the sequence tab instead of Source.
11. Fixed crops break when browser zoom changes. Detect boxes per screen state.
12. Image-box detector fails on video posts and light-background grids. Merge same-box states, fall back to a looser crop or a hold, never to camera.
13. Tattoo shots drifting onto the next post in reels → per-reel clamp.
14. Fixed face-crop guesses off by up to 200 px → detect per shot.
15. Energy-only silence trimming chops words → trim only between ASR words.
16. ffmpeg mp4 straight to the drive can corrupt → render local, copy, md5.
17. Overwriting files on the drive can silently fail → new names.
18. Background/parallel ffmpeg on huge camera files crawls → foreground, sequential.
19. Handles from memory are wrong → read from the screen.
20. Chapters < 10 s get dropped by YouTube → merge.
21. Banter title over a tattoo thumbnail → mismatch, lower CTR.
22. YouTube can't swap a video file after upload → cold open has to be in before upload.
23. Mics crash/overwrite happens (R72, R77) → screen-rec fallback.
24. OBS may roll late or stop early; a camera may stop early (R79 093A stopped at 24:40) → builder must swap to another angle when a source runs out.

---

## 14. Automation candidates (prioritized)

Build these as one Python package/CLI in a git repo **off the NLJBS Drive** (e.g. `~/Code/nljbs-tools`), with a `CLAUDE.md` holding the rules above. **First task: collect the scattered scripts** from `*/_claude_work/`, `_youtube/`, and `OPUS CLIPS/_assets/` into the repo, then generalize them. Per-episode settings go in a small config file (`episode.yaml`: release number, date, recording folder, mic files + who's on each, cameras + who's in each, OBS file, guest handles), auto-filled where possible and confirmed by Avery.

| # | Tool | What it does | Why first |
|---|---|---|---|
| 1 | **`nljbs probe <folder>`** | Inventory the recording folder: ffprobe every file (fps, codec, pix_fmt, color tags, duration, audio layout), detect mic form (GarageBand export vs raw .band), propose release number, write a draft `episode.yaml`, render a contact sheet of one frame per camera so roles can be confirmed. Flags oddities (119.88p, untagged color, dual-mono, a source that stops early). | Cheap, catches the R80-class surprises before any build. |
| 2 | **`nljbs sync`** | §4 method end to end → `_SYNCED.xml` per §5 spec, with residual re-measure from the written XML and a confidence/drift report. Screen-rec fallback flag. | The recurring heavy lift; fully specified; pure win. |
| 3 | **`nljbs xml lint` / `xml fix`** | Validates any xmeml: clipitem name = file name, pproTicks consistent with in/out, 29.97 NTSC everywhere, pathurl encoding, mics on mono tracks, ≤ 2 intro music pairs, V1 = ANG 1 to the end, no stray Lumetri. `fix` repairs track bumps, renames, ticks, strips grades. | Every color/sync disaster so far would have been caught. Run on every build and every Avery export. |
| 4 | **`nljbs transcribe`** | Parakeet (or mlx-whisper) on the mic mix → `words.json` with per-word speaker from mic levels, FIX map applied, plus a readable transcript with speaker labels and timestamps. | Feeds titles, trailer, chapters, reels. |
| 5 | **`nljbs map`** | Episode map: pre-show/body/outro bounds, OBS screen states, artist sections with handles read from the IG header (OCR on full-res OBS frames), proposed chapters. | Feeds switcher, description, reels. |
| 6 | **`nljbs chapters <final.mp4>`** | Audio-match Avery's export against the mics → final-cut time map → description with chapters (≥ 10 s each) in the §9 template. | Done by hand every single week. |
| 7 | **`nljbs publish`** | Wrap `post_shorts_v2.py`, `upload_episode.py`, `send_to_drive_v2.py` into one command with dry-run default, auto-picks the next free Short slot, creates Nick's Drive date folder, logs what was posted. Real run needs Avery's confirmation. | Already working; consolidation + scheduling logic. |
| 8 | **`nljbs reels`** | Generalize the R80 reels pipeline (specs → plan → ass → render → verify) driven by `episode.yaml` + a reel spec file, with the verify report and contact sheets always produced. Takes Avery's final XML to avoid cut material. | Biggest time sink after sync; pipeline exists. |
| 9 | **`nljbs switcher`** | Generalize `build80.py`/`plan80.py`: angle set generated from the cast config, speaker switching, screen-state layouts, holds, handle cards, intro copy + ep-number patch, cold-open builder from a list of phrase ranges, outro graphics. V11 off by default. Output always passes `xml lint`. | Highest value but most complex; do after 1–5 exist. |
| 10 | **`nljbs carryover`** | Diff Avery's edited XML vs the build (by nest in-point) and re-apply his edits onto a rebuilt/remade sequence; re-point mics to new exports. | Needed whenever a build gets redone mid-edit. |
| 11 | **`nljbs thumb`** | Thumbnail generator (§9) from the final export: candidate face frames by loudness/expression + face detection, tattoo card + IG header card, short hook text; outputs 2–3 variants. | Avery isn't happy with vidIQ thumbnails. |
| 12 | **`nljbs titles`** | Pull candidate hooks from the transcript + map, rank against the CTR rules. (Mostly a prompt for Claude, plus vidIQ score check if the vidIQ MCP is set up.) | Fast win once transcripts exist. |
| 13 | **`nljbs run <folder>`** | Orchestrates 1→2→4→5→(titles/thumb)→9→8 with checkpoints, notifying Avery when the sync XML is ready. | The end goal: "do Shop Talk." |
| 14 | Premiere MCP (optional) | Community Premiere MCP servers exist (e.g. github.com/leancoderkavy/premiere-pro-mcp). Use only for post-edit cleanup (reading the timeline, markers, handle-card fixes) on a **duplicate sequence**. Keep big builds as XML — MCP was reported unreliable for ripple deletes, razor cuts, effect writes on Premiere 26.3, and undo can break. | Test on a copy of R79 first. |
| 15 | Opus API | Only if Avery wants Opus back for topic picks / extra clips. | Lowest priority. |

Suggested order of work: **1 → 2 → 3 → 4 → 6 → 7**, then 5, 8, 9, 10, 11–13.

### Acceptance checks to bake in
- Sync residual ≤ 20 ms at 3 points from the written XML; coarse confidence reported per source.
- Every XML passes `xml lint` before it's handed over.
- Reels: caption timing median ≤ 0.05 s / p90 ≤ 0.12 s, no luma dips, −14 LUFS ±0.2, contact sheet produced.
- Descriptions: chapters ≥ 10 s, start at 0:00, handles match the screen.
- Never writes over an existing file on the drive.

---

## 15. Episode history (for reference)

| Rel | Recording | Cast | Notes |
|---|---|---|---|
| R70 | 08.31 | Nick + guests | Finished edit in VIDEOS FOR TRAINING (24:47) |
| R72 | 08.31.25 | — | Mic WAVs lost, screen-rec reference |
| R73–R75 | 09.07.26 | Nick (mic 1), AC (mic 2), Porter (mic 3) | Three takes same day |
| R76 | 10.05.26 | Nick, AC, Porter | First auto cut, raw `#` mic files; 17:22. "The Best Back Piece You'll Ever See" |
| R77 | 10.05.26 | Nick, AC, Porter | Mics crashed → OBS reference; switcher born; 23:25. "This Wolf Tattoo Leaves No Witnesses" (@mactyretattoo, @tad_dc, @justinweatherholtz) |
| R78 | 10.05.26 pt 3 | Nick + two guests | Handle-card rule, raw-mic switching, cold open, own reels; 21:22. @chadchesko, @tiger_ramos, @stewart_modernclassic |
| R79 | 10.26.26 RECORDING 1 | Porter (mic 1) hosts, AC (mic 2) | No Nick; hype trailer; Nick-requested recut to 14:23. @cum_eels, @smithtattoosf |
| R80 | 10.26.26 RECORDING 2 | Porter (mic 1), AC (mic 2), Jake Hawk (mic 3, couch) | Color/master-clip saga, GarageBand-export rule; final 23:03. @matty_d_mooney, @jeremiahbarba, @cololopeztattoo |

Detailed per-release build notes (offsets, sections, angle times) are in the NLJBS PODCAST project files: `knowledge/claude/shop-talk-r78-build.md`, `-r79-build.md`, `-r80-build.md`, plus `nljbs-production-playbook.md`, `shop-talk-editing-style.md`, `nljbs-reel-style.md`. Copies ship next to this file in `docs/`; put them in the repo's `docs/` folder.
