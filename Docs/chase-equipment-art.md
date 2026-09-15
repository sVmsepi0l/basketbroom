# chase equipment visuals

the four original wings were imported, attached to the compiled native balls
and reviewed in actual UE5.8 pie renders on september 12, 2026. the snipe and
snitch now have outward-facing wings with distinct copper and ivory treatments.
these are provisional equipment assets; packaged visual review, performance
measurement and a finished surface/hinge art pass remain outstanding.

`Tools/build_chase_equipment.py --generate-source` authors four original obj
meshes in `SourceArt/Equipment`. explicit editor operation `build` imports the
meshes into `/Basketbroom/Art/Equipment` in the UE5.8 project. the importer checks
ownership metadata before replacement and saves only those four assets.

the snipe uses broader copper wings; the snitch uses longer, narrower ivory
wings around its gold body. each wing contains a swept spar and eight separate
vanes. the authored wing spans are approximately 83 cm for the snipe and 105 cm
for the snitch, including vane tips. left and right meshes preserve mirrored
triangle winding. their authored units are centimeters, and the source manifest
records geometry counts, bounds and sha-256 hashes.

the installed legacy obj import path reflects source y even with scene conversion
disabled. the first native render exposed wings pointing inward across the ball,
which made the visible span appear too short. the read-only
`Tools/probe_native_chase_bounds.py` established the y reflection from signed
asset bounds, while component world scale was 1 on all wings. the generator now
authors the inverse y orientation for each named wing before import. imported
left wings extend toward native -y and right wings toward +y; the existing
runtime hinges and ball scale remain unchanged. the final bounds report matches
the expected obj y reflection within approximately 0.000001 cm for all four
assets. it is not a runtime scaling workaround.

`bbball` attaches both wings to the existing smoothed visual mesh. absolute
component scale retains the authored dimensions despite the smaller ball mesh.
the wings have no collision, overlap events or navigation contribution. visual
heading follows visible travel; mirrored local rotations flap at five cycles
per second for the live snipe and seven for the live snitch, with slower idle
movement. no additional network messages carry these cosmetic rotations.

the native 28 cm chase-ball radius, 380 cm capture range, eligibility, continuous
hold, server flight speed and custody/scoring logic are unchanged. wing tips do
not enlarge the catch target.

the corrected snipe front and three-quarter renders are in
`.local/art-review/chase/1789218915496015800/`; the corresponding snitch renders
are in `.local/art-review/chase/1789218949833519600/`. reviewed three-quarter
copies are checked in as [native Snipe](Screenshots/native-snipe.png) and
[native Snitch](Screenshots/native-snitch.png). both show outward wings in the
real arena. the snitch body remains strongly emissive, and the separated vanes
and simple attachment need further art work.

`Tools/preview_native_chase.py` captures an existing native pie ball and records
its mesh/material/collision configuration and changing flap angle. to repeat:

1. with pie stopped on bb_regulation, request `{"operation":"prepare"}`. this
   stages one explicitly tagged, **unsaved non-transient editor camera** so the
   engine will duplicate it into PIE. a transient editor actor was omitted from
   pie duplication in this engine build.
2. start native PIE. for the verified normal-speed practice launch, use
   `native_play_session.py` with `{"operation":"start","practice":true}`.
   that temporarily changes the live editorengine launch url, restores it once
   the native context exists, and checks actual `bpractice`; it changes no time
   dilation or rule state.
3. run the preview with `{"operation":"start","ball_index":3}` for an active
   Snipe. for the snitch, use `{"operation":"start","ball_index":4,
   "pause_on_release":true}`. this waits for natural activation, then queues an
   ordinary host stoppage and captures the ball there. it does not force release
   or freeze an actor's tick. the final snitch run took 67.812 wall seconds,
   including the natural practice release, and captured status STOPPAGE.
4. the helper borrows the tagged pie camera, moves only that camera, exports two
   1280×960 views, detaches/releases its render target, and leaves the session at
   the requested stoppage. it never assigns a gameplay actor's transform,
   capture progress, clock, score or activation. read
   `.local/native-chase-preview.json`; the tool's `captured_pending_visual_review`
   status still requires a person or agent to inspect the exported images.
5. end pie, then request `{"operation":"cleanup"}` to remove the unsaved editor
   camera before any save or cook. the helper saves no map. camera insertion can
   mark the map dirty; there is no intended map change to retain. the completed
   review session closed the editor without saving these fixtures and restored
   the previous standalone play mode.

the final snitch report observed visible nocollision wings, the expected ivory
material and world scale 1. its recorded flap range was about -33.69 to +9.97
degrees across the live-to-stoppage transition and capture. this establishes
native cosmetic motion in that session; it does not certify sustained live flap
frequency, physical piloting, gameplay capture mechanics or packaged rendering.
