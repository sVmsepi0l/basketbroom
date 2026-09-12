# Chase equipment visuals

The four original wings were imported, attached to the compiled native balls
and reviewed in actual UE5.8 PIE renders on September 12, 2026. The Snipe and
Snitch now have outward-facing wings with distinct copper and ivory treatments.
These are provisional equipment assets; packaged visual review, performance
measurement and a finished surface/hinge art pass remain outstanding.

`Tools/build_chase_equipment.py --generate-source` authors four original OBJ
meshes in `SourceArt/Equipment`. Explicit editor operation `build` imports the
meshes into `/Basketbroom/Art/Equipment` in the UE5.8 project. The importer checks
ownership metadata before replacement and saves only those four assets.

The Snipe uses broader copper wings; the Snitch uses longer, narrower ivory
wings around its gold body. Each wing contains a swept spar and eight separate
vanes. The authored wing spans are approximately 83 cm for the Snipe and 105 cm
for the Snitch, including vane tips. Left and right meshes preserve mirrored
triangle winding. Their authored units are centimeters, and the source manifest
records geometry counts, bounds and SHA-256 hashes.

The installed legacy OBJ import path reflects source Y even with scene conversion
disabled. The first native render exposed wings pointing inward across the ball,
which made the visible span appear too short. The read-only
`Tools/probe_native_chase_bounds.py` established the Y reflection from signed
asset bounds, while component world scale was 1 on all wings. The generator now
authors the inverse Y orientation for each named wing before import. Imported
Left wings extend toward native -Y and Right wings toward +Y; the existing
runtime hinges and ball scale remain unchanged. The final bounds report matches
the expected OBJ Y reflection within approximately 0.000001 cm for all four
assets. It is not a runtime scaling workaround.

`BBBall` attaches both wings to the existing smoothed visual mesh. Absolute
component scale retains the authored dimensions despite the smaller ball mesh.
The wings have no collision, overlap events or navigation contribution. Visual
heading follows visible travel; mirrored local rotations flap at five cycles
per second for the live Snipe and seven for the live Snitch, with slower idle
movement. No additional network messages carry these cosmetic rotations.

The native 28 cm chase-ball radius, 380 cm capture range, eligibility, continuous
hold, server flight speed and custody/scoring logic are unchanged. Wing tips do
not enlarge the catch target.

The corrected Snipe front and three-quarter renders are in
`.local/art-review/chase/1789218915496015800/`; the corresponding Snitch renders
are in `.local/art-review/chase/1789218949833519600/`. Reviewed three-quarter
copies are checked in as [native Snipe](Screenshots/native-snipe.png) and
[native Snitch](Screenshots/native-snitch.png). Both show outward wings in the
real arena. The Snitch body remains strongly emissive, and the separated vanes
and simple attachment need further art work.

`Tools/preview_native_chase.py` captures an existing native PIE ball and records
its mesh/material/collision configuration and changing flap angle. To repeat:

1. With PIE stopped on BB_Regulation, request `{"operation":"prepare"}`. This
   stages one explicitly tagged, **unsaved non-transient editor camera** so the
   engine will duplicate it into PIE. A transient editor actor was omitted from
   PIE duplication in this engine build.
2. Start native PIE. For the verified normal-speed practice launch, use
   `native_play_session.py` with `{"operation":"start","practice":true}`.
   That temporarily changes the live EditorEngine launch URL, restores it once
   the native context exists, and checks actual `bPractice`; it changes no time
   dilation or rule state.
3. Run the preview with `{"operation":"start","ball_index":3}` for an active
   Snipe. For the Snitch, use `{"operation":"start","ball_index":4,
   "pause_on_release":true}`. This waits for natural activation, then queues an
   ordinary host stoppage and captures the ball there. It does not force release
   or freeze an actor's tick. The final Snitch run took 67.812 wall seconds,
   including the natural practice release, and captured status STOPPAGE.
4. The helper borrows the tagged PIE camera, moves only that camera, exports two
   1280×960 views, detaches/releases its render target, and leaves the session at
   the requested stoppage. It never assigns a gameplay actor's transform,
   capture progress, clock, score or activation. Read
   `.local/native-chase-preview.json`; the tool's `captured_pending_visual_review`
   status still requires a person or agent to inspect the exported images.
5. End PIE, then request `{"operation":"cleanup"}` to remove the unsaved editor
   camera before any save or cook. The helper saves no map. Camera insertion can
   mark the map dirty; there is no intended map change to retain. The completed
   review session closed the editor without saving these fixtures and restored
   the previous Standalone play mode.

The final Snitch report observed visible NoCollision wings, the expected ivory
material and world scale 1. Its recorded flap range was about -33.69 to +9.97
degrees across the live-to-stoppage transition and capture. This establishes
native cosmetic motion in that session; it does not certify sustained live flap
frequency, physical piloting, gameplay capture mechanics or packaged rendering.
