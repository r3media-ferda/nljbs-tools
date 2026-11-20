# R3 Media short-form style (Avery's cut)

Measured 2026-11-19 from Avery's own Premiere exports. Use this as the target when building or reviewing any vertical short for an R3 client (Pale Fire, NLJBS, Dayton Market, Being Financial and the rest).

## Sources

| Set | Where | Count |
|---|---|---|
| Avery's edits, Jan 2025 to Sep 2025 | `/Volumes/Extreme SSD/PREMIERE PRO ARCHIEVE` | 86 vertical shorts |
| Avery's edits, Apr 2025 to Nov 2026 | `/Volumes/NLJBS Drive/Premire pro arcive` | 93 vertical shorts |
| Pale Fire reference | `/Volumes/Extreme SSD/R3 Media/PALE FIRE/2026/VIDEO AUTOMATION /STIENHOLDING.xml` | 1 timeline |

172 unique shorts after dropping duplicates. **Ignore `/Volumes/Extreme SSD/R3 Media/Reels Archive`**: OpusClip output, not Avery's cutting.

Measurement code and raw data: `~/r3-work/style/` (`measure.py`, `measurements_all.json`, frame sheets in `sheets/`). Shot boundaries come from PySceneDetect with the taste-distillation adaptive threshold, so punch-ins and hard camera moves count as cuts.

## Rhythm

Stable across every period from Jan 2025 to 2026. Treat these as the house numbers.

| Metric | Target | Range seen (p25 to p75) |
|---|---|---|
| Reel length | 18 s | 13 to 29 s; 97 of 172 run under 20 s, 18 run over 45 s |
| Shot length | 0.8 s median | 0.47 to 1.57 s; p95 3.7 s |
| Cuts per minute | about 50 | 2026 work runs 58 |
| Longest shot in a reel | about 4 s | a hold past 4 s needs a payoff (a laugh, a reveal, a reaction) |
| First cut | 1.0 to 1.4 s | 2026 opens at 0.98 s median with 3 cuts in the first 3 s |
| Last shot | about 1.2 s | retail clients extend this with an end card |

Trend: the 2026 edits open faster and hold less (p95 shot 2.9 s against 3.7 s before). Build new work to the 2026 numbers.

**Do not chase the 0.8 s median by cutting speech.** The median counts punch-ins inside lines. Avery rejected the first automated Pale Fire drafts (2026-11-19) as rushed, with words and sentences cut short. Generated cuts keep whole sentences with breathing room: about 0.2 s before the first word and 0.35 s after the last. Beat-snapping may trim only the silence beyond those pads. One subject per reel (one brewer per taste-test video).

## Captions

- On every reel with speech. Music-only pieces (STIENHOLDING) carry none.
- 1 to 3 words per card, timed to the word, centered, about 60% down the frame.
- Font follows the client: condensed gothic (blackletter) in white with a dark edge for NLJBS and tattoo content; script or serif for Dayton Market; bold serif for Green Hummingbird; clean sans for plain promo text ("POV: TRAINING WITH JESS").
- Pale Fire has no caption font on record yet. Ask Avery before the first captioned Pale Fire reel.
- NLJBS reels add red keywords (see `nljbs/reels.py`).

## Graphics

Light by design. Avery does not run graphics-heavy edits, so do not add motion graphics, animated titles, emoji or stickers.

- Tattoo or product photos cut in full frame, or as an inset with a thin white border over the talking head.
- Retail clients (Dayton Market, fashion show) end on a branded card: logo, hours, address, date. NLJBS and Pale Fire end on content.
- One static text line at most for a POV or title.

## Picture

- Talking heads get punch-ins on emphasis, which drives the fast shot median.
- Cut on words: the Dayton Christmas reel hands one sentence across 6 people, one word each.
- Tight framing; the speaker fills the frame.

## Audio

Loudness has been inconsistent: median -16.2 LUFS, with reels from -22 to -12.6 LUFS and peaks touching 0 dBFS. The 2026 work sits at -19.4 LUFS, quiet against other reels in a feed.

Target from now: **-14 LUFS integrated, true peak at or below -1 dBTP**, the same as `nljbs reels`.

## Format

1080x1920. Exports mix 30, 29.97 and 23.976 fps; for direct-to-MP4 shorts pick one rate per reel and let ffmpeg conform. Premiere-bound XML stays at 29.97 (`timebase 30`, `ntsc TRUE`).

## Delivery (Rella)

`<id>_FINAL.mp4` is the master. Upload `<id>_SOCIAL.mp4` from `palefire social`: H.264 High, 29.97 fps, broadcast range BT.709, video capped at 12 Mbps, AAC 128 kbps 48 kHz, index at the front, 3 to 90 s. That meets Instagram Reels (25 Mbps, 128 kbps audio, 300 MB caps) and Facebook Reels (3 to 90 s). Canon MP4s are full range; the SOCIAL export converts them to broadcast range so platforms do not crush blacks.

Rella imports media only from a public link. `palefire serve <files>` serves only those files through a Cloudflare quick tunnel, checks each link, and closes after the import (or after 10 minutes). Captions and Rella content IDs live in the shoot plan (`caption:`, `rella:`). Drafts go in unscheduled with auto-publish off; Avery sets the date and turns on auto-publish.

## Pale Fire

### Music-driven event piece (STIENHOLDING, Oktoberfest, 63 s)

| Time | Beat | How |
|---|---|---|
| 0 to 15 s | Build | One take (the emcee) cut into 9 pieces, punch-ins climbing 156% to 168% to 183% to 184%. Canon 4K b-roll laid over on V3 twice. |
| 15 to 17 s | Stutter | 5 cuts of 0.2 to 0.7 s, zoom climbing 146% to 283%. Signature move. |
| 17 s | Ramp | 150% speed, clip audio muted. |
| 17 to 33 s | Montage | 1.5 to 4 s shots on the music. |
| 33 to 59 s | Payoff | Two long holds with natural sound up (11.6 s and 9.5 s). |
| 59 to 63 s | Stills | Four event photos, about 1 s each, scaled to fit. |

Music sits about 3.7 dB down the whole way (level 0.65), re-edited with two crossfades so a section lands on the payoff. Natural sound comes up only on chosen clips. Median shot 1.33 s: slower than the talking reels because the long holds carry it.

### Speech-driven series (Nov 11 blindfold tasting)

One video per taster. Captions, a punch-in on each guess, whole sentences, and a hold on the reveal reaction. A running score counter ("n/3" with three dots that turn green or red) updates on each reveal. Cold-open on the strongest line. Beer names, as written on the glasses: Negative Boogie, Hazy Bayse, Boogie Nights; Simple Man is also on tap. Canon Log footage needs the C-Log3 LUT before anything else (see `palefire probe`).
