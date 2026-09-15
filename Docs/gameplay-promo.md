# prototype gameplay demo

the current position showcase contains **222 seconds of gameplay**, landscape
**3840 × 2160 (4k), 16:9, 60 fps**, with a six-second illustrated intro and a
twelve-second matching outro for a **4:00 complete promo**. it demonstrates the current alpha's native gameplay,
with staged camera work and automated inputs. it does not claim final art,
internet multiplayer or completed hogwarts legacy integration.

use footage from the actual UE5.8 basketbroom game, including arena/team flight,
scoring-ball play, chase balls, and the working wand/referee features. the
director records observed gameplay events and labels camera/actor staging.
do not present intended input requests as successful goals, catches or spells.
generated screenshots and cinematic mockups are not substitutes for gameplay.
creator kit footage is separate and does not establish standalone game behavior.

the standard director remains 180 seconds; `showcase_positions: true` adds three
14-second role vignettes for a 222-second take. video frame
zero and the director's timestamp origin must align. verify the actual footage,
legibility, sequence duration and frame continuity before delivery. retain the
native frames, event manifest, audio receipt and edit commands for reproduction.
exports include a clean 4k master and a review version with brief chapter
captions. the clean version retains the game's own hud during gameplay inserts.
source frames and local production receipts stay under `.local/gameplay-demo/`.

## capture workflow

build the editor target with `Build-Native.ps1 -target editor`, then open the
UE5.8 project with the existing editor bridge and select `BB_Regulation`.
the `basketbroomcapture` module and sequencerscripting plugin are editor-only;
they are not dependencies of the packaged game.

the bridge scripts run in this order:

1. `gameplay_demo_capture.py`: `prepare` with `fps: 60` and a fresh `.local` output directory.
   it creates its own practice pie viewport. wait for the capture report to
   show `ready`.
2. `gameplay_demo_director.py`: `prepare`, then `start`. this starts capture at
   the director's recorded time origin, runs the configured shot sequence and
   stops its owned pie world when finished. do not start a separate playtest
   inside that world.
3. check the director's `complete` result and all gameplay checks, plus capture
   `captured`, native resource size `3840 × 2160`, matching written/frame counts
   and an empty protocol failure reason. inspect the actual frames as well.
4. mix the original cues, then use `Tools/assemble_gameplay_demo.py` with the
   capture, director and audio receipts. keep both the clean and captioned MP4s.

for the position take, prepare the director with `showcase_positions: true`,
`duration_seconds: 222`, `rehearsal: false` and `capture_sync: true` after the
capture helper reports ready. pass `--duration 222` to both the mixer and
assembler, and `--gameplay-seconds 222` to the bookend finisher. native 4K/60 fps,
frame count and audio duration remain required; this is a fresh take with its
own event timestamps, not a retimed edit of the preceding gameplay.

`ubbviewportcaptureprotocol` reads the actual game viewport's render texture.
the stock legacy frame grabber sampled the smaller preview-window backbuffer
and clamped its edge pixels into nominal 4k frames on this machine. the custom
protocol refuses a render resource whose dimensions differ from the requested
capture, and reports completed asynchronous image writes. the preview window's
display size does not determine the recorded resolution.

for a rehearsal, start a fresh practice pie session, then prepare the director
with `capture_sync: false, rehearsal: true`. this compresses camera holds to
99 seconds while preserving real spell cooldowns, catch holds and the natural
60-live-second practice snitch release. rehearsals are not accepted as final
video/audio manifests. disposable actor positions, movement settings, camera
state and the temporary background-throttle setting are restored or destroyed
with the owned session. no editor map or content asset is saved.

## edited audio

`Tools/mix_gameplay_demo_audio.py` assembles a **48 khz stereo pcm16 wav** from
the four original repository clips in `SourceArt/Audio`. it consumes observed
director events and places cues at their exact offsets, quantized to the nearest
audio sample. native pickup/throw/goal/catch gains follow `BBAudioFeedback.cpp`.
mark showcased events `featured: true`; incidental goals remain audible at a
lower level. catch events include the native catch and score cues. unmapped
events, including input requests and spells without an original audio cue,
stay silent.

this is a **sparse edited game-cue mix**, not a recording of unreal's audio
output. it uses no external music, microphone audio or system audio. no original
arena-wind loop exists in the current source folder, so none is added. the
generated `.mix.json` receipt records source hashes, exact sample placements,
gains, ignored events, format checks and sample-peak headroom. listening and
audiovisual synchronization still require review.

```powershell
python Tools/mix_gameplay_demo_audio.py --manifest .local/gameplay-demo-director.json
```

default output is `.local/gameplay-demo/basketbroom-prototype-demo-audio.wav`.
numpy is required; no unreal session is needed. assemble that wav with the video
only after the event manifest describes the finished take. the mixer requires
`status: complete` and rejects rehearsal manifests.

## feature cards and controller segment

`Tools/gameplay_demo_cards.py` draws the revised cards as native-resolution ass
text and vector shapes. headlines use 84 px bold type and descriptions use
54 px, increased from 58 / 34 px. shorter, two-line descriptions sit on dark
panels with colored accents and brief fades. regular cards occupy about 5.5% of
the frame and remain visible for six seconds. the referee and final-result
cards move lower to keep the native dialogs readable.

all added editorial text is lowercase, including card headlines, descriptions,
controller labels, title/outro copy, displayed links and technology badges.
normalize visible copy before ass escaping and text measurement. keep native
in-game HUD/environment lettering as captured, official icon artwork unchanged,
and exact destination urls, source identifiers and font names intact.

an eight-second controller section runs at **00:19–00:27** over the existing
automated flight footage. it shows a generic gamepad icon, implemented stick /
cast / shield mappings, the user's confirmed dualsense usb triangle input, and
the remaining usb / bluetooth testing. this is support information, not a new
physical-controller recording or a claim that all hardware combinations pass.

the position edition contains 23 cards. each of the six positions receives two
seven-second phases: purpose and ball permissions, then a useful rule or limit.
counts in the headings reflect the eight-player team (one netminder, two chasers,
one trapper, one ranger, two hurleybacks and one Scout). the existing controller
insert remains at 00:19–00:27 of gameplay / 00:25–00:33 of the complete promo.

netminder, chaser and trapper vignettes occupy gameplay 00:28–00:42,
00:42–00:56 and 00:56–01:10. each records an actual accepted role change at an
official stoppage, an arranged inbound scoring-ball pickup, native flight while
carrying, ordinary release and free flight. their stopped portraits/tails keep
the extra live play within practice's first quarter. no scores, custody or rule
clocks are assigned. ranger is restored before the original scoring sequence;
all original events from 00:28 onward move 42 seconds later in the director.

ranger, hurleyback and scout role cards use their actual existing scenarios at
01:45, 02:02 and 03:13 of the new gameplay timeline. the hurleyback now holds
long enough to show the native two-second warning, then releases before the
three-second limit. source checks distinguish actual role actions from intended
inputs and from the tactical descriptions in the cards. trapper stripping and
hurley striking/pocket animations are not claimed as implemented mechanics.

to revise captions without another gameplay capture or clean-master encode,
pass `--review-from` the previous export json and choose a fresh `--name`:

```powershell
python Tools/assemble_gameplay_demo.py `
  --capture .local/gameplay-demo/take-01/capture.json `
  --manifest .local/gameplay-demo/take-01/director.json `
  --review-from "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/12\basketbroom-prototype-4k-export.json" `
  --output-dir "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/12" `
  --name basketbroom-prototype-4k-v2
```

reuse validates the original capture/director provenance and freshly probes
the clean file. it preserves the audio, records source hashes and produces a
new review mp4, captions and export receipt, including the exact review encoder
arguments and working directory. the clean master and earlier
review remain available.

the delivered `basketbroom-prototype-4k-v2-review.mp4` passed a complete video /
audio decode and fresh 4k / 30 fps / 5,400-frame / 180-second stream checks.
its audio matches the clean master. fourteen nonoverlapping card intervals,
including the two controller phases, match the exported ass and receipt.
card previews and selected final encoded frames were inspected for clipping,
readability and unobstructed native referee/result dialogs. the local
`basketbroom-prototype-4k-v2-validation.json` records independent checks.

## red-rock intro and outro

`Tools/finish_gameplay_promo.py` adds a **6-second intro** and **12-second outro**
to the completed 180-second 4k60 review. the same illustrated american southwest
red-rock artwork appears at both ends. the intro names basketbroom and describes
the broom flight, ball play and spellwork; the outro adds the five requested
social/project destinations and official brand marks. all intro/outro text
uses **google sans flex black (weight 900)**, as requested in the final typography
revision; `SourceArt/Promo/Fonts` preserves the exact font and license/source details.
the compositor loads the supplied static black face directly, verifies the
renderer selected it, and measures the actual title to retain the approved
visual size across fonts. no system font installation is required.

the current southwest illustration is
`SourceArt/Promo/basketbroom-redrock-cliff-alcove-keyart-v2.png`: rust-red sandstone,
a broad natural overhang enclosing the arena, and puebloan-style adobe terraces.
the northern alternative, `basketbroom-redwoods-coast-keyart-v1.png`, shows
old-growth coast redwoods and a pacific cove inspired by northern california
and southern Oregon. matching title/outro stills are available for both.

the built-in imagegen tool edited both illustrations from the preceding plates.
both have a native size of 1672 × 941; the compositor fits each illustration to the 4k
bookends and typesets text and icons at 4K. this artwork does not represent
the current in-game arena or final game assets. full generation/edit prompts
and first-party icon sources are retained under `SourceArt/Promo`.

the technology badge reads **hogwarts legacy creator kit mod in development**
and **prototype built in unreal engine 5.8**. the gameplay in this video comes
from the standalone UE5.8 prototype; it does not establish a completed hlck port.

```powershell
python Tools/finish_gameplay_promo.py `
  --gameplay "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/13-Lowercase\basketbroom-prototype-4k60-lowercase-review.mp4" `
  --art SourceArt/Promo/basketbroom-redrock-cliff-alcove-keyart-v2.png `
  --output-dir "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026/09/13-Lowercase" `
  --name basketbroom-prototype-4k60-lowercase
```

use `--prepare-only` with a fresh output name to render the editable layout and
intro/outro pngs before the gameplay is ready. `--layout` accepts the emitted
json for later changes and normalizes its visible text to lowercase before
measurement and rendering. `--preflight` runs a short, explicitly synthetic
concatenation fixture in an empty directory; it is never a gameplay delivery.

the final assembly stream-copies all 10,800 gameplay video frames and encodes
only the bookends. it verifies frame counts, timestamps and non-key video
packet hashes; H.264 container conversion may insert SPS/PPS headers at key
frames. audio is decoded and encoded once more to aac with exactly six seconds
of leading silence and twelve seconds after gameplay. there is no gameplay
frame interpolation, doubling, scaling, or audio gain adjustment at this step.
cards and cue times move exactly six seconds later in the complete promo.

the production receipt includes media probes, hashes, commands, art fitting,
icon provenance and packet checks. retain the clean gameplay master, separate
cue wav, chapter ass, bookend pngs, layout json and both bookend ass files for
the user's edit. decode the finished file and inspect actual encoded frames
before delivery.

## delivery

### current six-position showcase

the expanded delivery is in
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-Positions\`.
`basketbroom-prototype-4k60-positions.mp4` is the complete **4:00** southwest
promo. matching `-clean.mp4` and `-review.mp4` files contain **222 seconds** of
fresh gameplay, with 23 cards in the review. each of netminder, chaser, trapper,
ranger, hurleyback and scout has two seven-second explanations covering its
purpose, ball permissions and relevant rules. all added copy stays lowercase.

the new netminder, chaser and trapper vignettes demonstrate native incoming-ball
pickup, movement-input carry and ordinary release with measured free flight.
the expanded hurleyback sequence shows the native two-second warning and a
release **2.35 seconds** after the observed pickup, before the three-second
limit. wider camera angles keep the rider and equipment visible during carries.
incoming trajectories are staged; protected restarts, teammate pass receptions,
dedicated trapper stripping and hurley strike animations are not demonstrated.

the fresh take at `.local/gameplay-demo/take-positions-01` passed **80/80 native
gameplay checks** and reached the certified **232–37** result. its independent
source audit passed **20/20 checks**, including all **13,338 distinct native
3840 × 2160 jpegs**, contiguous numbering and matching capture counters. the
edit uses the first 13,320 frames; the last 18 are the natural capture shutdown
tail. the editor reported no dirty maps or content after capture.

the fresh 48 khz stereo cue mix has **16 placements** from this take's observed
events and no clipping. the delivery includes source receipts, cue wav, card
timings, editable bookends and production-script snapshots. the approved
cliff-alcove/adobe illustration, google sans flex black typography, official
social icons and controller insert are retained. earlier videos remain available.

the completed promo passed **61/61 independent media checks**: full video/audio
decode, exactly **14,400 frames / 240 seconds at 60 fps**, all **13,320 gameplay
picture payloads preserved at +6 seconds**, fresh capture and encoder provenance,
six complete role-card pairs, lowercase copy and valid bookend links. all 16
audio placements align at zero sample lag, and both bookends are silent. aac
changes sample values slightly without editorial gain changes. the adjacent
visual receipt records inspection of both phases of every role, encoded role,
referee and result samples, and both encoded bookends.

### earlier lowercase revision

the preceding delivery is in
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-Lowercase\`.
`basketbroom-prototype-4k60-lowercase.mp4` is the complete 3:18 southwest promo;
`basketbroom-prototype-4k60-lowercase-review.mp4` is the 180-second gameplay edit.
both use lowercase editorial copy. matching `-intro.png` and `-outro.png` files
provide the southwest bookends; `basketbroom-redwoods-coast-lowercase-intro.png`
and `-outro.png` provide the northern alternate.

the review was freshly encoded from the original clean 4k60 master with only
the new ass cards as a visual filter, preserving native HUD/environment case
and copying the audio. the final assembly preserves all 10,800 new review
picture payloads at +6 seconds. the earlier uppercase versions are retained.

independent validation passed **74/74 checks**: all 14 card intervals and 30
visible card text rows, lowercase bookends, original destination urls, clean
source/encoder provenance, complete video/audio decode, 11,880 frames at 60 fps,
198 seconds, exact audio agreement with the prior promo, ten cues with zero
sample lag and silent bookends. fresh encoded controller/role/referee/result
frames, both encoded southwest bookends and the northern stills passed visual
inspection. the adjacent media and visual receipts record the evidence.

### native 60 fps take and illustrated promo

the 2026/09/13 take in `.local/gameplay-demo/take-60-01` completed **44/44
observed gameplay checks**, ending **232–37**. its capture audit verified all
**10,818 frames** at native **3840 × 2160**, with contiguous names and **10,818
distinct sha256 hashes**. the first **10,800 frames** supply exactly 180 seconds
at 60 fps; the remaining 18 are the natural 0.3-second shutdown tail.

capture and director origins match exactly. the owned editor exited normally,
practice url and background throttle were restored, and no dirty map/content
packages remained. `native-60fps-validation.json` and `source-frames.sha256`
record the source audit. the new take's event manifest drives its own audio
mix; the prior 30 fps event timings and wav are not reused.

the delivered `basketbroom-prototype-4k60-promo.mp4` is **198 seconds**, **11,880
frames**, 4k60, with matching red-rock bookends in **google sans flex Black**.
it lives under `%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-4K60\`.
the folder also holds the 180-second clean and captioned gameplay exports,
editable bookend PNGs/ASS/layout, fonts and official icons, the separate cue wav,
source receipts, editing notes and selected encoded frames used for visual QA.

all 10,800 gameplay picture payloads are unchanged in the final assembly, with
timestamps shifted exactly six seconds. the full final file decodes without
errors; all ten audio placements align at zero sample lag, and the bookends
are silent. aac encoding changes sample values slightly, as documented in the
audio/production receipts. both encoded bookends and selected controller,
position, referee and result-card frames were visually inspected. independent
media and visual validation receipts are alongside the video.

the earlier `basketbroom-prototype-4k60-complete` files retain the superseded
Georgia/Segoe typography intermediate. the **`-promo`** prefix identifies the
google sans flex black version before the environment revision. no social uploads were performed.

the later environment revision lives in
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/13-Environment-v2\`.
its southwest video is `basketbroom-prototype-4k60-cliff-alcove.mp4`, using the
same validated gameplay/card source with revised red-rock cliff-alcove and adobe
bookends. `basketbroom-redwoods-coast-intro.png` and `-outro.png` provide the
northern alternative as paired stills. both retain the exact google sans flex
black layout, official social icons and development-status badge. source
rasters remain 1672 × 941; the still art is fitted to the 4k bookends.
the environment revision passed **63/63 independent media checks**, including
full decode, all gameplay picture payloads unchanged and exact audio agreement
with the previous validated promo. new encoded southwest bookends and the
redwoods still layout were visually inspected. its receipts and editing notes
are in the new delivery folder; earlier videos remain available.

### earlier 30 fps versions

the first full take on 2026/09/12 completed **44/44 observed gameplay checks**
and reached a certified **232–37 teal win** after the snitch catch. the capture
protocol wrote all **5,409 native 3840 × 2160 frames** with no failure. the edit
uses the first 5,400 frames for exactly 180 seconds at 30 fps; the extra nine
frames are a natural shutdown tail, not padding. practice url and background
throttle settings were restored, and the editor reported no dirty map or content
packages after the owned capture session ended.

the clean and captioned review mp4s were exported to
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026/09/12\` as
`basketbroom-prototype-4k-clean.mp4` and
`basketbroom-prototype-4k-review.mp4`. both stream inspections confirm 3840 × 2160,
30 fps and 5,400 frames / 180 seconds. the folder also contains chapter captions,
editing notes, an export receipt, and a `source` folder with the separate stereo
wav and production receipts. raw jpeg frames remain in the repository's ignored
`.local/gameplay-demo/take-01/frames` directory.

the capture addition passed both editor and game target builds. selected source
frames and decoded review frames were inspected for native framing, hud and
caption legibility, spell/referee feedback, catches and the certified result.
the complete review mp4 decoded without errors. both exports' audio starts at
zero and spans exactly 180 seconds; all ten cue placements matched the edited
wav at zero sample lag. this numerical alignment check is separate from
subjective listening. the independent validation receipt is beside the videos.

this showcase verifies the staged sequence's outcomes, not the completeness of
all regulation rules, internet multiplayer, or physical controller coverage.
the usb dualsense triangle check is recorded separately in the controller guide.

the user authorized creating this prototype demo for potential social-media
use. **uploading or publishing it to social accounts is not authorized.**
review the completed exports with the user before any separate publishing step.
