# Oz's editing workflow

Oz's editing expertise, in his words. Claude reads this before cutting anything, alongside `docs/R3_SHORT_FORM_STYLE.md`. When the two disagree, ask Avery and Oz which one wins, then fix the loser.

How to add to it: tell Claude in plain words ("when I cut a recap, I always...", "for night footage I...") and ask it to write it here and commit it. Keep each rule short, say why, and add an example shoot or reel when there is one.

## Reference work

Oz's finished reels: `/Volumes/2026-27/R3/DAYTON MARKET/10.OCT/10.2 MEDIA DAY/VIDEO/EDITED` (Dayton Market media day, Oct 2026, 7 vendor reels). Look at these when you need to see how Oz edits.

What Claude measured from them on 2026-11-24 (Claude's notes, not Oz's words; check with Oz before treating any of it as a rule):

| Reel | Length | Kind | Captions |
|---|---|---|---|
| KK-FALL DRINKS | 47 s | vendor talks, then a drink-making b-roll montage | only while she talks |
| RWD-Xmas Sneak Peek | 111 s | one locked-off take of the vendor unboxing, no cuts | all the way through |
| SMK-FALL GOODS | 24 s | vendor talks, cuts away to the product she names | all the way through |
| TTT-THUNDAYYY REEL | 11 s | store b-roll, comedy text bit | text is the joke |
| TTT-WORLD SMALLEST REEL | 20 s | vendor talks, overhead product shots | all the way through |
| WVJ FALL DECOR | 23 s | music-only store b-roll | none |
| ZOLAS FALL DECOR | 26 s | music-only product b-roll, fades to black at the end | none |

- Shots hold 2 to 5 s, with slow handheld pushes on products. That's slower than Avery's 0.8 s median: Oz lets the product and the person breathe.
- Captions are white serif, 1 to 5 words, with a soft shadow (SMK uses a dark rounded box). Placement moves shot to shot so they never cover the face or the product, mostly in the upper third.
- When a vendor names a product, the cut goes to that product (SMK, TTT-WORLD SMALLEST).
- Exports: 1080x1920, 30 fps, H.264 about 20 Mbps, AAC 320 kbps 48 kHz.
- Loudness runs from -28 to -13 LUFS between reels. Normalize to the house -14 LUFS when Claude builds Oz-style reels.

November finals: `/Volumes/2026-27/R3/DAYTON MARKET/11.NOV/11.6 MEDIA DAY/VIDEO/3_FINALS` (9 files; `NOV REELS.mp4` looks like a second export of `KK FALL DRINKS.mp4`). These are newer, so where they differ from October, follow these.

| Reel | Length | Kind |
|---|---|---|
| ZOLAS THANKSGIVING REEL | 21 s | owner opens with a question ("Hey, everyone. Are you hosting Thanksgiving..."), cuts to each product as she names it, ends back on her |
| SMK PUMPKIN TREATS | 47 s | vendor walks the case, cuts to each product and to the pre-order flyer |
| SMK NEW FLAVORS | 20 s | vendor talks plus product shots |
| TTT ABOUT US | 113 s | the owners tell the store's story: two speakers, b-roll and old photos |
| KK FALL DRINKS | 19 s | one macro shot of a drink being built, music only, no captions |
| NRL Mallar Ducks, TTT TURKEYS, Warfels Autumn Pizza | 9 to 10 s | quick single-product pieces |

- **Captions now take the vendor's brand color:** pink for Sweet Molly Kate's, red for Zola's, light blue for the toy store, each with a white or dark edge. Still serif, still 1 to 5 words. In these, they sit near the middle of the frame, not in the upper third.
- **Size emphasis:** sometimes one word in a card is set smaller or bigger than the rest ("We have *little* pumpkin").
- **Talking reels open on the voice:** a greeting or a question to the viewer, not an action shot. This matches Oz's "hooks are audio based."
- **Bookends:** Zola's starts and ends on the speaker, which helps the reel loop.
- **Loudness:** -22 to -14 LUFS, and several reels peak above 0 dBFS. Claude's builds stay at -14 LUFS with true peak at or below -1 dBTP.

## How Oz cuts

In Oz's words:

> I always cut and align audio before I color or find music, unless the video requires a specific song. Once it is cut, aligned, and colored, I'll add the captions and make sure they're placed correctly. Lastly, if needed, I'll make a title screen/graphic to start the video or serve as a reel cover on socials.

Order for Claude to follow:

1. Cut and align the audio. Exception: if the video is built around a specific song, start from the song.
2. Color.
3. Music (when it wasn't picked first).
4. Captions, then check every card's placement.
5. Title screen or graphic, only if the video needs one: an opening card or a reel cover for socials.

## Pacing and structure

In Oz's words:

> Hooks are more audio based rather than an action. I would like to meet in the middle with the shot length. As far as music, I try to cut on beat if there is a strong bass line or percussion. The 11 s video is an anomaly; I try to keep everything under a minute. No logos or store info, but adding market hours at the end of reels sounds like a good idea. I like to make reels loopable when possible. Especially if it's audio only, I will ask Epidemic to make the audio loopable using their AI features.

Rules for Claude:

- **Hook:** open on the strongest line or sound, not on an action shot. Pick the hook by what you hear in the first seconds.
- **Shot length:** between Avery's 0.8 s median and Oz's 2 to 5 s holds. Aim for about 1.5 to 2.5 s, and confirm with Oz on the first cuts.
- **Beat cutting:** snap cuts to the beat only when the track has a strong bass line or percussion. On soft or ambient tracks, cut by feel and don't force beat snapping.
- **Length:** under 60 s. Very short pieces (like the 11 s TTT reel) are the exception.
- **Ending:** no logo or store-info card. End with the market hours. Make the reel loop when possible: the last shot and sound should lead back into the first.
- **Loopable music:** for music-only reels, use Epidemic Sound's AI tools to get a loopable version of the track.
- **Open question (Avery and Oz):** `R3_SHORT_FORM_STYLE.md` says retail clients like Dayton Market end on a branded card with logo, hours, address and date. Oz wants market hours only, with no logo or store info. Decide which wins, then fix the other doc.

## Color and look

In Oz's words:

> I mainly use a Sony a7 III in S-Log3. I bounce between LUT #1 and #2. I will usually apply the LUT and then edit highlights, shadows and exposure. Most of the time I will add a slight S-curve to bring in some contrast. I try to go for a bright and warm look. I will rarely mix cameras or lighting in a video; usually everything is shot in the same environment with the same settings and camera. Using store colors in the captions is a new rule I have been following: either matching it to the store's branding or, if it's an Xmas reel, using Xmas colors.

Rules for Claude:

- **Source:** Sony a7 III, S-Log3 / S-Gamut3.Cine. Treat any untagged flat a7 III footage as S-Log3.
- **LUTs:** Sony's look profiles. Oz's two are in the repo, so `palefire cut` can use them on either Mac (`clip_lut: luts/sony/<name>.cube`):
  - `luts/sony/1_SGamut3CineSLog3_To_LC-709.cube`
  - `luts/sony/2_SGamut3CineSLog3_To_LC-709TypeA.cube`

  The full Sony set (including #3 and #4) is in `/Volumes/2026-27/!ASSETS/VIDEO/LUTS/SonyLookProfiles_SLog3_SGamut3Cine`.

  There's no fixed default: render a frame with each and pick the one that suits the shoot. #3 and #4 aren't part of his look.
- **Grade order:** LUT, then exposure, highlights and shadows, then a slight S-curve for contrast.
- **Look:** bright and warm.
- **Matching:** one camera, one environment and one setting per video, so one grade per reel is the norm. Flag any clip that doesn't match instead of grading it separately without saying so.
- **Caption color (new rule):** match the store's branding: the color from their logo or sign. On Christmas reels, use Christmas colors instead.

## Audio

In Oz's words:

> Almost always an on-camera shotgun mic. I'll clean up audio with the Premiere Essential Sound tab to remove loud humming and external noise. I pick music usually by mood; I try to go for more country songs or pop. If it's a montage reel of products, I'll do some slower music with more percussion. Seasonal music is also good. Stores like Tic Tac Toys almost always get something more upbeat and pop because that's their vibe, and Kaffee Klatsch will usually get lo-fi music. I will mess with audio levels and fix by ear. I will try and find fun audio bits like pouring or an entrance bell, usually from Epidemic's database. I don't aim for any loudness.

Rules for Claude:

- **Dialogue:** on-camera shotgun. Clean it the way Essential Sound does: take out hum (a high-pass around 80 Hz, plus a notch at 60 Hz if hum is still there) and background noise, gently. Don't make the voice sound thin or watery.
- **Music by mood:** country or pop by default. Product montages get slower tracks with strong percussion. Seasonal music works whenever it fits. Per store:
  - Tic Tac Toys: upbeat pop.
  - Kaffee Klatsch: lo-fi.
- **Sound bits:** add small real sounds where they fit: a pour, the entrance bell. Pull them from Epidemic Sound's SFX library.
- **Loudness standard (Oz asked Claude to set one, 2026-11-24).** Instagram and TikTok don't publish an official target. -14 LUFS with a -1 dBTP ceiling is the common convention and matches YouTube's guidance, so it's the house number for every Oz reel:

  | What | Target |
  |---|---|
  | Whole export | -14 LUFS integrated (±1) |
  | True peak | -1 dBTP or lower; nothing touches 0 |
  | Music under talking | about 18 dB below the voice (sources say 18 to 25 dB); duck it, don't sit it flat |
  | Music with no one talking | bring it back up; it can carry the reel |
  | Sound bits | audible but under the voice; set by ear |
  | Export audio | AAC, 48 kHz, stereo, 128 kbps or more |

  Platforms turn loud uploads down but don't turn quiet ones up. A -28 LUFS reel plays very quiet next to everything else in the feed. Above about -14 LUFS, the platform just turns it down and the peaks may crush.
- **In Premiere:** tag dialogue and music in Essential Sound, use Auto-Duck on the music, and run Loudness Auto-Match to -14 LUFS when exporting (Export settings › Effects › Loudness Normalization, ITU BS.1770-3, -14 LUFS, -1 dBTP).
- **Claude's builds:** `palefire cut --preview` already mixes to -14 LUFS / -1 dBTP.

Sources (checked 2026-11-24): [vloggingpro.com audio loudness](https://vloggingpro.com/tools/audio-loudness/), [OpenClip audio normalization](https://openclip.app/learn/audio-normalization), [Gearnews on the loudness war](https://www.gearnews.com/loudness-war/), [Descript audio levels](https://www.descript.com/blog/article/how-to-set-the-perfect-audio-levels-for-video), [Vidpros on music too loud](https://vidpros.com/fix-background-music-too-loud-video/).

## Captions and text

In Oz's words:

> Keep the fonts and placement the same as Avery had them. Keep placement as close to 40% down the screen, preferably below the subject's face. I use Premiere's auto caption generator and then fix things from there. Keep it around 15 characters per caption and try to keep things like store names or products in the same caption frame instead of splitting them. I'm open to new ways to animate captions, whether that's changing font size and color or other suggestions.

Rules for Claude:

- **Font:** per client (see Per client): Palatino for Dayton Market, Montserrat for Pale Fire; otherwise Avery's fonts in `R3_SHORT_FORM_STYLE.md`. Color follows the store's branding (see Color and look).
- **Placement:** about 40% down the frame (y ≈ 770 of 1920), below the speaker's face. If a face or the product sits there, nudge the card down rather than covering it, and stay inside the Reels safe zone (y 270 to 1250, clear of the right-side buttons). This replaces Avery's 60% for Oz's reels.
- **Source:** Premiere auto-captions, then fix by hand. Claude starts from the ASR words and fixes spelling of store names, products and people the same way.
- **Card length:** about 15 characters per card. Never split a store name or product name across two cards ("Sweet Molly Kate's", "pumpkin roll", "Tic Tac Toys" stay whole), even if a card runs a bit long.
- **Animation (Oz is open to trying these; confirm on the first reels):**
  1. **Pop in:** each card scales from 90% to 100% over 3 to 4 frames. Subtle, reads as alive.
  2. **Keyword color:** store and product names in the store's brand color; the other words in white. Like the red NLJBS keywords, but brand-colored.
  3. **Keyword size:** the store or product name about 15% bigger than the rest of the card (Oz already does the opposite on small words, as in "We have *little* pumpkin").
  4. **Active word:** the word being spoken lights up in the brand color while the rest of the card stays white. Good for slower talkers.

  Keep it to one or two of these per reel. Avery's style is light on graphics: no bouncing, emoji or stickers.

### Title cards and reel covers

Oz makes these in Canva. Example: `~/Downloads/Your paragraph text.mp4` (Redbanks Christmas Giveaway, 1080x1920, 5.3 s, static):

- Background: a product photo from the shoot, blurred and darkened under a green tint, so the text reads.
- Type stack, centered: a heavy slab serif in the store's brand color (maroon) with a white edge for the name and the key line ("REDBANKS", "Winner's Prize"), mixed with a white retro script for the softer lines ("Christmas Giveaway", "every", "entry"). Prices and numbers big.
- One seasonal graphic at the top (Christmas ornaments).
- Text runs from about 23% to 85% down the frame, inside the Reels safe zone.
- Only when the video needs one: an opening card, or a cover for socials.

## Per client

In Oz's words:

> The font for Dayton should be Palatino. Redbanks and Whiskey Valley Jerky are definitely country vibes. SMK would be more upbeat as well. Zola's a little slower. Market holiday hours are Tuesday–Saturday 9am–6pm until Christmas. Keep Montserrat for Pale Fire.

### Dayton Market

- **Caption font:** Palatino (comes with macOS: `/System/Library/Fonts/Palatino.ttc`), in the store's brand color.
- **End card, holiday hours (until 2026-12-25):** `Tuesday–Saturday 9am–6pm`. After Christmas, ask Oz for the regular hours before putting hours on a reel.
- **Music by store:**

  | Store | Vibe |
  |---|---|
  | Tic Tac Toys (TTT) | upbeat pop |
  | Sweet Molly Kate's (SMK) | upbeat |
  | Kaffee Klatsch (KK) | lo-fi |
  | Redbanks | country |
  | Whiskey Valley Jerky (WVJ) | country |
  | Zola's | a little slower |
  | Others | by mood: country or pop, slower with percussion for product montages |

### Pale Fire

- **Caption font:** Montserrat, which is what `palefire cut` already uses. (Oz first said Roca from Adobe Fonts, then decided to keep Montserrat.)

## Never do

In Oz's words:

> I will usually cut out the first and last second of b-roll since it's shaky from me pressing the record button. If clips are in 120 fps they can be slowed down if it's b-roll to make it smoother. When exporting, start with the store's abbreviation such as TTT or SMK followed by what the reel is about.

Rules for Claude:

- **Trim b-roll:** drop the first and last second of every b-roll clip (the shake from pressing record). Never use those frames, even when a clip is short.
- **120 fps b-roll:** slow it down (120 into a 30 fps timeline plays at 25%, or pick a speed between that and 100% to fit the beat). Only on b-roll: talking shots play at normal speed.
- **File names:** `<STORE> <WHAT IT'S ABOUT>.mp4`, starting with the store's abbreviation, for example `TTT TURKEYS.mp4`, `SMK PUMPKIN TREATS.mp4`, `ZOLAS THANKSGIVING REEL.mp4`. Store codes seen so far: TTT (Tic Tac Toys), SMK (Sweet Molly Kate's), KK (Kaffee Klatsch), WVJ (Whiskey Valley Jerky), RWD (Rusty Willow Decor), NRL, ZOLAS, Warfels, Redbanks.
- **Finals folder:** `<month folder>/<date> MEDIA DAY/VIDEO/3_FINALS` (as in `11.NOV/11.6 MEDIA DAY`).

### Export settings (Premiere, Oz's current preset, 2026-11-24)

| Setting | Value |
|---|---|
| Format | H.264, 1080x1920, 30 fps, progressive, square pixels |
| Quality | Render at Maximum Depth on, Use Maximum Render Quality on, Time Interpolation: Frame Sampling |
| Encoding | Software encoding, profile High, level 4.1, Rec. 709 |
| Bitrate | VBR 2-pass, target 10 Mbps, max 13 Mbps |
| Key frames | default |
| Audio, Captions, Effects | on |

Notes for Claude:

- This preset fits Instagram and Facebook Reels (25 Mbps cap). `palefire social` re-encodes to its own 12 Mbps cap if a reel goes through Rella.
- The October and November finals were exported at about 20 Mbps with 320 kbps audio, so this 10/13 Mbps preset is newer.
- Under Effects, turn on Loudness Normalization at -14 LUFS / -1 dBTP (see Audio).
- The Captions section is switched on. If it's set to burn in Premiere's caption track on top of designed captions, the words will show twice. Check before export.
