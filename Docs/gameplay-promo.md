# Three-minute prototype gameplay demo

The prototype showcase targets **three minutes**, landscape **3840 × 2160
(4K), 16:9, 30 fps**. It demonstrates the current alpha's native gameplay,
with staged camera work and automated inputs. It does not claim final art,
internet multiplayer or completed Hogwarts Legacy integration.

Use footage from the actual UE5.8 Basketbroom game, including arena/team flight,
scoring-ball play, chase balls, and the working wand/referee features. The
director records observed gameplay events and labels camera/actor staging.
Do not present intended input requests as successful goals, catches or spells.
Generated screenshots and cinematic mockups are not substitutes for gameplay.
Creator Kit footage is separate and does not establish standalone game behavior.

The capture pipeline targets 180 seconds at 30 frames per second. Video frame
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

1. `gameplay_demo_capture.py`: `prepare` with a fresh `.local` output directory.
   It creates its own Practice PIE viewport. Wait for the capture report to
   show `ready`.
2. `gameplay_demo_director.py`: `prepare`, then `start`. This starts capture at
   the director's recorded time origin, runs the 180-second shot sequence and
   stops its owned PIE world when finished. Do not start a separate playtest
   inside that world.
3. Check the director's `complete` result and all gameplay checks, plus capture
   `captured`, native resource size `3840 × 2160`, matching written/frame counts
   and an empty protocol failure reason. Inspect the actual frames as well.
4. Mix the original cues, then use `Tools/assemble_gameplay_demo.py` with the
   capture, director and audio receipts. Keep both the clean and captioned MP4s.

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

An eight-second controller section runs at **00:19–00:27** over the existing
automated flight footage. It shows a generic gamepad icon, implemented stick /
cast / shield mappings, the user's confirmed DualSense USB Triangle input, and
the remaining USB / Bluetooth testing. This is support information, not a new
physical-controller recording or a claim that all hardware combinations pass.

To revise captions without another gameplay capture or clean-master encode,
pass `--review-from` the previous export JSON and choose a fresh `--name`:

```powershell
python Tools/assemble_gameplay_demo.py `
  --capture .local/gameplay-demo/take-01/capture.json `
  --manifest .local/gameplay-demo/take-01/director.json `
  --review-from "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026-09-12\basketbroom-prototype-4k-export.json" `
  --output-dir "$env:USERPROFILE\Videos\Basketbroom\Prototype-2026-09-12" `
  --name basketbroom-prototype-4k-v2
```

Reuse validates the original capture/director provenance and freshly probes
the clean file. It preserves the audio, records source hashes and produces a
new review MP4, captions and export receipt. The clean master and earlier
review remain available.

The delivered `basketbroom-prototype-4k-v2-review.mp4` passed a complete video /
audio decode and fresh 4K / 30 fps / 5,400-frame / 180-second stream checks.
Its audio matches the clean master. Fourteen nonoverlapping card intervals,
including the two controller phases, match the exported ASS and receipt.
Card previews and selected final encoded frames were inspected for clipping,
readability and unobstructed native referee/result dialogs. The local
`basketbroom-prototype-4k-v2-validation.json` records independent checks.

## Delivery

The first full take on 2026-09-12 completed **44/44 observed gameplay checks**
and reached a certified **232–37 Teal win** after the Snitch catch. The capture
protocol wrote all **5,409 native 3840 × 2160 frames** with no failure. The edit
uses the first 5,400 frames for exactly 180 seconds at 30 fps; the extra nine
frames are a natural shutdown tail, not padding. Practice URL and background
throttle settings were restored, and the editor reported no dirty map or content
packages after the owned capture session ended.

The clean and captioned review MP4s were exported to
`%USERPROFILE%\Videos\Basketbroom\Prototype-2026-09-12\` as
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
