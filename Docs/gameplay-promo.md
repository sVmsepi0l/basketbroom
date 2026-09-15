# Prototype gameplay demo

The current position showcase contains **222 seconds of gameplay**, landscape
**3840 × 2160 (4K), 16:9, 60 fps**, with a six-second illustrated intro and a
twelve-second matching outro for a **4:00 complete promo**. It demonstrates the current alpha's native gameplay,
with staged camera work and automated inputs. It does not claim final art,
internet multiplayer or completed Hogwarts Legacy integration.

Use footage from the actual UE5.8 Basketbroom game, including arena/team flight,
scoring-ball play, chase balls, and the working wand/referee features. The
director records observed gameplay events and labels camera/actor staging.
Do not present intended input requests as successful goals, catches or spells.
Generated screenshots and cinematic mockups are not substitutes for gameplay.
Creator Kit footage is separate and does not establish standalone game behavior.

The standard director remains 180 seconds; `showcase_positions: true` adds three
14-second role vignettes for a 222-second take. Video frame
zero and the director's timestamp origin must align. Verify the actual footage,
legibility, sequence duration and frame continuity before delivery. Retain the
native frames, event manifest, audio receipt and edit commands for reproduction.
Exports include a clean 4K master and a review version with brief chapter
captions. The clean version retains the game's own HUD during gameplay inserts.
Source frames and local production receipts stay under `.local/gameplay-demo/`.

## Capture workflow

Build the Editor target with `Build-Native.ps1 -Target Editor`, then open the
UE5.8 project with the existing editor bridge and select `BB_Regulation`.
The `BasketbroomCapture` module and SequencerScripting plugin are Editor-only;
they are not dependencies of the packaged game.

The bridge scripts run in this order:

1. `gameplay_demo_capture.py`: `prepare` with `fps: 60` and a fresh `.local` output directory.
   It creates its own Practice PIE viewport. Wait for the capture report to
   show `ready`.
2. `gameplay_demo_director.py`: `prepare`, then `start`. This starts capture at
   the director's recorded time origin, runs the configured shot sequence and
   stops its owned PIE world when finished. Do not start a separate playtest
   inside that world.
3. Check the director's `complete` result and all gameplay checks, plus capture
   `captured`, native resource size `3840 × 2160`, matching written/frame counts
   and an empty protocol failure reason. Inspect the actual frames as well.
4. Mix the original cues, then use `Tools/assemble_gameplay_demo.py` with the
   capture, director and audio receipts. Keep both the clean and captioned MP4s.

For the position take, prepare the director with `showcase_positions: true`,
`duration_seconds: 222`, `rehearsal: false` and `capture_sync: true` after the
capture helper reports ready. Pass `--duration 222` to both the mixer and
assembler, and `--gameplay-seconds 222` to the bookend finisher. Native 4K/60 fps,
frame count and audio duration remain required; this is a fresh take with its
own event timestamps, not a retimed edit of the preceding gameplay.

`UBBViewportCaptureProtocol` reads the actual game viewport's render texture.
The stock legacy frame grabber sampled the smaller preview-window backbuffer
and clamped its edge pixels into nominal 4K frames on this machine. The custom
protocol refuses a render resource whose dimensions differ from the requested
capture, and reports completed asynchronous image writes. The preview window's
display size does not determine the recorded resolution.

For a rehearsal, start a fresh Practice PIE session, then prepare the director
with `capture_sync: false, rehearsal: true`. This compresses camera holds to
99 seconds while preserving real spell cooldowns, catch holds and the natural
60-live-second Practice Snitch release. Rehearsals are not accepted as final
video/audio manifests. Disposable actor positions, movement settings, camera
state and the temporary background-throttle setting are restored or destroyed
with the owned session. No editor map or content asset is saved.

## Edited audio

`Tools/mix_gameplay_demo_audio.py` assembles a **48 kHz stereo PCM16 WAV** from
the four original repository clips in `SourceArt/Audio`. It consumes observed
director events and places cues at their exact offsets, quantized to the nearest
audio sample. Native pickup/throw/goal/catch gains follow `BBAudioFeedback.cpp`.
Mark showcased events `featured: true`; incidental goals remain audible at a
lower level. Catch events include the native catch and score cues. Unmapped
events, including input requests and spells without an original audio cue,
stay silent.

This is a **sparse edited game-cue mix**, not a recording of Unreal's audio
output. It uses no external music, microphone audio or system audio. No original
arena-wind loop exists in the current source folder, so none is added. The
generated `.mix.json` receipt records source hashes, exact sample placements,
gains, ignored events, format checks and sample-peak headroom. Listening and
audiovisual synchronization still require review.

```powershell
python Tools/mix_gameplay_demo_audio.py --manifest .local/gameplay-demo-director.json
```

Default output is `.local/gameplay-demo/basketbroom-prototype-demo-audio.wav`.
NumPy is required; no Unreal session is needed. Assemble that WAV with the video
only after the event manifest describes the finished take. The mixer requires
`status: complete` and rejects rehearsal manifests.

## Feature cards and controller segment

`Tools/gameplay_demo_cards.py` draws the revised cards as native-resolution ASS
text and vector shapes. Headlines use 84 px bold type and descriptions use
54 px, increased from 58 / 34 px. Shorter, two-line descriptions sit on dark
panels with colored accents and brief fades. Regular cards occupy about 5.5% of
the frame and remain visible for six seconds. The referee and final-result
cards move lower to keep the native dialogs readable.

All added editorial text is lowercase, including card headlines, descriptions,
controller labels, title/outro copy, displayed links and technology badges.
Normalize visible copy before ASS escaping and text measurement. Keep native
in-game HUD/environment lettering as captured, official icon artwork unchanged,
and exact destination URLs, source identifiers and font names intact.

An eight-second controller section runs at **00:19–00:27** over the existing
automated flight footage. It shows a generic gamepad icon, implemented stick /
cast / shield mappings, the user's confirmed DualSense USB Triangle input, and
the remaining USB / Bluetooth testing. This is support information, not a new
physical-controller recording or a claim that all hardware combinations pass.

The position edition contains 23 cards. Each of the six positions receives two
seven-second phases: purpose and ball permissions, then a useful rule or limit.
Counts in the headings reflect the eight-player team (one Netminder, two Chasers,
one Trapper, one Ranger, two Hurleybacks and one Scout). The existing controller
insert remains at 00:19–00:27 of gameplay / 00:25–00:33 of the complete promo.

Netminder, Chaser and Trapper vignettes occupy gameplay 00:28–00:42,
00:42–00:56 and 00:56–01:10. Each records an actual accepted role change at an
official stoppage, an arranged inbound scoring-ball pickup, native flight while
carrying, ordinary release and free flight. Their stopped portraits/tails keep
the extra live play within Practice's first quarter. No scores, custody or rule
clocks are assigned. Ranger is restored before the original scoring sequence;
all original events from 00:28 onward move 42 seconds later in the director.

Ranger, Hurleyback and Scout role cards use their actual existing scenarios at
01:45, 02:02 and 03:13 of the new gameplay timeline. The Hurleyback now holds
long enough to show the native two-second warning, then releases before the
three-second limit. Source checks distinguish actual role actions from intended
inputs and from the tactical descriptions in the cards. Trapper stripping and
Hurley striking/pocket animations are not claimed as implemented mechanics.

To revise captions without another gameplay capture or clean-master encode,
pass `--review-from` the previous export JSON and choose a fresh `--name`:

```powershell
python Tools/assemble_gameplay_demo.py `
  --capture .local/gameplay-demo/take-01/capture.json `
  --manifest .local/gameplay-demo/take-01/director.json `
  --review-from "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/12\basketbroom-prototype-4k-export.json" `
  --output-dir "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/12" `
  --name basketbroom-prototype-4k-v2
```

Reuse validates the original capture/director provenance and freshly probes
the clean file. It preserves the audio, records source hashes and produces a
new review MP4, captions and export receipt, including the exact review encoder
arguments and working directory. The clean master and earlier
review remain available.

The delivered `basketbroom-prototype-4k-v2-review.mp4` passed a complete video /
audio decode and fresh 4K / 30 fps / 5,400-frame / 180-second stream checks.
Its audio matches the clean master. Fourteen nonoverlapping card intervals,
including the two controller phases, match the exported ASS and receipt.
Card previews and selected final encoded frames were inspected for clipping,
readability and unobstructed native referee/result dialogs. The local
`basketbroom-prototype-4k-v2-validation.json` records independent checks.

## Red-rock intro and outro

`Tools/finish_gameplay_promo.py` adds a **6-second intro** and **12-second outro**
to the completed 180-second 4K60 review. The same illustrated American Southwest
red-rock artwork appears at both ends. The intro names Basketbroom and describes
the broom flight, ball play and spellwork; the outro adds the five requested
social/project destinations and official brand marks. All intro/outro text
uses **Google Sans Flex Black (weight 900)**, as requested in the final typography
revision; `SourceArt/Promo/Fonts` preserves the exact font and license/source details.
The compositor loads the supplied static Black face directly, verifies the
renderer selected it, and measures the actual title to retain the approved
visual size across fonts. No system font installation is required.

The current Southwest illustration is
`SourceArt/Promo/basketbroom-redrock-cliff-alcove-keyart-v2.png`: rust-red sandstone,
a broad natural overhang enclosing the arena, and Puebloan-style adobe terraces.
The northern alternative, `basketbroom-redwoods-coast-keyart-v1.png`, shows
old-growth coast redwoods and a Pacific cove inspired by northern California
and southern Oregon. Matching title/outro stills are available for both.

The built-in imagegen tool edited both illustrations from the preceding plates.
Both have a native size of 1672 × 941; the compositor fits each illustration to the 4K
bookends and typesets text and icons at 4K. This artwork does not represent
the current in-game arena or final game assets. Full generation/edit prompts
and first-party icon sources are retained under `SourceArt/Promo`.

The technology badge reads **hogwarts legacy creator kit mod in development**
and **prototype built in unreal engine 5.8**. The gameplay in this video comes
from the standalone UE5.8 prototype; it does not establish a completed HLCK port.

```powershell
python Tools/finish_gameplay_promo.py `
  --gameplay "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/13-Lowercase\basketbroom-prototype-4k60-lowercase-review.mp4" `
  --art SourceArt/Promo/basketbroom-redrock-cliff-alcove-keyart-v2.png `
  --output-dir "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/13-Lowercase" `
  --name basketbroom-prototype-4k60-lowercase
```

Use `--prepare-only` with a fresh output name to render the editable layout and
intro/outro PNGs before the gameplay is ready. `--layout` accepts the emitted
JSON for later changes and normalizes its visible text to lowercase before
measurement and rendering. `--preflight` runs a short, explicitly synthetic
concatenation fixture in an empty directory; it is never a gameplay delivery.

The final assembly stream-copies all 10,800 gameplay video frames and encodes
only the bookends. It verifies frame counts, timestamps and non-key video
packet hashes; H.264 container conversion may insert SPS/PPS headers at key
frames. Audio is decoded and encoded once more to AAC with exactly six seconds
of leading silence and twelve seconds after gameplay. There is no gameplay
frame interpolation, doubling, scaling, or audio gain adjustment at this step.
Cards and cue times move exactly six seconds later in the complete promo.

The production receipt includes media probes, hashes, commands, art fitting,
icon provenance and packet checks. Retain the clean gameplay master, separate
cue WAV, chapter ASS, bookend PNGs, layout JSON and both bookend ASS files for
the user's edit. Decode the finished file and inspect actual encoded frames
before delivery.

## Delivery

### Current six-position showcase

The expanded delivery is in
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-Positions\`.
`basketbroom-prototype-4k60-positions.mp4` is the complete **4:00** Southwest
promo. Matching `-clean.mp4` and `-review.mp4` files contain **222 seconds** of
fresh gameplay, with 23 cards in the review. Each of Netminder, Chaser, Trapper,
Ranger, Hurleyback and Scout has two seven-second explanations covering its
purpose, ball permissions and relevant rules. All added copy stays lowercase.

The new Netminder, Chaser and Trapper vignettes demonstrate native incoming-ball
pickup, movement-input carry and ordinary release with measured free flight.
The expanded Hurleyback sequence shows the native two-second warning and a
release **2.35 seconds** after the observed pickup, before the three-second
limit. Wider camera angles keep the rider and equipment visible during carries.
Incoming trajectories are staged; protected restarts, teammate pass receptions,
dedicated Trapper stripping and Hurley strike animations are not demonstrated.

The fresh take at `.local/gameplay-demo/take-positions-01` passed **80/80 native
gameplay checks** and reached the certified **232–37** result. Its independent
source audit passed **20/20 checks**, including all **13,338 distinct native
3840 × 2160 JPEGs**, contiguous numbering and matching capture counters. The
edit uses the first 13,320 frames; the last 18 are the natural capture shutdown
tail. The editor reported no dirty maps or content after capture.

The fresh 48 kHz stereo cue mix has **16 placements** from this take's observed
events and no clipping. The delivery includes source receipts, cue WAV, card
timings, editable bookends and production-script snapshots. The approved
cliff-alcove/adobe illustration, Google Sans Flex Black typography, official
social icons and controller insert are retained. Earlier videos remain available.

The completed promo passed **61/61 independent media checks**: full video/audio
decode, exactly **14,400 frames / 240 seconds at 60 fps**, all **13,320 gameplay
picture payloads preserved at +6 seconds**, fresh capture and encoder provenance,
six complete role-card pairs, lowercase copy and valid bookend links. All 16
audio placements align at zero sample lag, and both bookends are silent. AAC
changes sample values slightly without editorial gain changes. The adjacent
visual receipt records inspection of both phases of every role, encoded role,
referee and result samples, and both encoded bookends.

### Earlier lowercase revision

The preceding delivery is in
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-Lowercase\`.
`basketbroom-prototype-4k60-lowercase.mp4` is the complete 3:18 Southwest promo;
`basketbroom-prototype-4k60-lowercase-review.mp4` is the 180-second gameplay edit.
Both use lowercase editorial copy. Matching `-intro.png` and `-outro.png` files
provide the Southwest bookends; `basketbroom-redwoods-coast-lowercase-intro.png`
and `-outro.png` provide the northern alternate.

The review was freshly encoded from the original clean 4K60 master with only
the new ASS cards as a visual filter, preserving native HUD/environment case
and copying the audio. The final assembly preserves all 10,800 new review
picture payloads at +6 seconds. The earlier uppercase versions are retained.

Independent validation passed **74/74 checks**: all 14 card intervals and 30
visible card text rows, lowercase bookends, original destination URLs, clean
source/encoder provenance, complete video/audio decode, 11,880 frames at 60 fps,
198 seconds, exact audio agreement with the prior promo, ten cues with zero
sample lag and silent bookends. Fresh encoded controller/role/referee/result
frames, both encoded Southwest bookends and the northern stills passed visual
inspection. The adjacent media and visual receipts record the evidence.

### Native 60 fps take and illustrated promo

The 2026/09/13 take in `.local/gameplay-demo/take-60-01` completed **44/44
observed gameplay checks**, ending **232–37**. Its capture audit verified all
**10,818 frames** at native **3840 × 2160**, with contiguous names and **10,818
distinct SHA256 hashes**. The first **10,800 frames** supply exactly 180 seconds
at 60 fps; the remaining 18 are the natural 0.3-second shutdown tail.

Capture and director origins match exactly. The owned editor exited normally,
Practice URL and background throttle were restored, and no dirty map/content
packages remained. `native-60fps-validation.json` and `source-frames.sha256`
record the source audit. The new take's event manifest drives its own audio
mix; the prior 30 fps event timings and WAV are not reused.

The delivered `basketbroom-prototype-4k60-promo.mp4` is **198 seconds**, **11,880
frames**, 4K60, with matching red-rock bookends in **Google Sans Flex Black**.
It lives under `%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-4K60\`.
The folder also holds the 180-second clean and captioned gameplay exports,
editable bookend PNGs/ASS/layout, fonts and official icons, the separate cue WAV,
source receipts, editing notes and selected encoded frames used for visual QA.

All 10,800 gameplay picture payloads are unchanged in the final assembly, with
timestamps shifted exactly six seconds. The full final file decodes without
errors; all ten audio placements align at zero sample lag, and the bookends
are silent. AAC encoding changes sample values slightly, as documented in the
audio/production receipts. Both encoded bookends and selected controller,
position, referee and result-card frames were visually inspected. Independent
media and visual validation receipts are alongside the video.

The earlier `basketbroom-prototype-4k60-complete` files retain the superseded
Georgia/Segoe typography intermediate. The **`-promo`** prefix identifies the
Google Sans Flex Black version before the environment revision. No social uploads were performed.

The later environment revision lives in
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-Environment-v2\`.
Its Southwest video is `basketbroom-prototype-4k60-cliff-alcove.mp4`, using the
same validated gameplay/card source with revised red-rock cliff-alcove and adobe
bookends. `basketbroom-redwoods-coast-intro.png` and `-outro.png` provide the
northern alternative as paired stills. Both retain the exact Google Sans Flex
Black layout, official social icons and development-status badge. Source
rasters remain 1672 × 941; the still art is fitted to the 4K bookends.
The environment revision passed **63/63 independent media checks**, including
full decode, all gameplay picture payloads unchanged and exact audio agreement
with the previous validated promo. New encoded Southwest bookends and the
redwoods still layout were visually inspected. Its receipts and editing notes
are in the new delivery folder; earlier videos remain available.

### Earlier 30 fps versions

The first full take on 2026/09/12 completed **44/44 observed gameplay checks**
and reached a certified **232–37 Teal win** after the Snitch catch. The capture
protocol wrote all **5,409 native 3840 × 2160 frames** with no failure. The edit
uses the first 5,400 frames for exactly 180 seconds at 30 fps; the extra nine
frames are a natural shutdown tail, not padding. Practice URL and background
throttle settings were restored, and the editor reported no dirty map or content
packages after the owned capture session ended.

The clean and captioned review MP4s were exported to
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/12\` as
`basketbroom-prototype-4k-clean.mp4` and
`basketbroom-prototype-4k-review.mp4`. Both stream inspections confirm 3840 × 2160,
30 fps and 5,400 frames / 180 seconds. The folder also contains chapter captions,
editing notes, an export receipt, and a `Source` folder with the separate stereo
WAV and production receipts. Raw JPEG frames remain in the repository's ignored
`.local/gameplay-demo/take-01/frames` directory.

The capture addition passed both Editor and Game target builds. Selected source
frames and decoded review frames were inspected for native framing, HUD and
caption legibility, spell/referee feedback, catches and the certified result.
The complete review MP4 decoded without errors. Both exports' audio starts at
zero and spans exactly 180 seconds; all ten cue placements matched the edited
WAV at zero sample lag. This numerical alignment check is separate from
subjective listening. The independent validation receipt is beside the videos.

This showcase verifies the staged sequence's outcomes, not the completeness of
all regulation rules, internet multiplayer, or physical controller coverage.
The USB DualSense Triangle check is recorded separately in the controller guide.

The user authorized creating this prototype demo for potential social-media
use. **Uploading or publishing it to social accounts is not authorized.**
Review the completed exports with the user before any separate publishing step.
