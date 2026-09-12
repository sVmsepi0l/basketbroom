# Skeletal rider authoring checkpoint

`Tools/stage_skeletal_rider.py` ran in UE5.8.1 on September 12, 2026. It staged the
installed stock dependencies and saved an original seated animation plus four
derived team material instances. Real front, side and three-quarter asset renders
were reviewed, the combined native C++ build succeeded, and the read-only native
PIE rider probe passed for all 16 riders. The final native gameplay capture shows
seated team-colored riders in the arena. This is a stock-character foundation,
not finished character art or an AAA graphics milestone.

## Exact source and output

The source is the locally installed Epic UE5.8 Third Person shared character
content at:

`C:\Program Files\Epic Games\UE_5.8\Templates\TemplateResources\High\Characters\Content\Mannequins`

The selected mesh is `Meshes/SKM_Quinn_Simple.uasset`; the shared skeleton is
`Meshes/SK_Mannequin.uasset`. A conservative scan of serialized package names
finds 23 installed packages totaling 81,908,625 bytes (about 78.1 MiB). That set
includes Manny Simple, both characters' materials/textures, the shared physics
asset and body Control Rig. The skeleton's preview references pull in both
meshes; copying only Quinn's mesh would leave references unresolved.

The explicit `build()` preserves their original
`/Game/Characters/Mannequins/` package paths in this UE5 project's Content folder.
It refuses to overwrite a differing local package. This is Epic stock content,
not original Basketbroom geometry and not Hogwarts Legacy content. The derived
team materials apply teal or copper paint, roughness 0.68 and metallic 0.18 to
the paint layer while preserving the stock surface maps. The stock UE logo
switch is disabled in these four derived instances.

The stock directory `DevelopmentHarness/Content/Characters/Mannequins` is a local
installed-template dependency, intended to be reconstructed rather than checked
into this repository. The generated animation and four owned material instances
under `DevelopmentHarness/Plugins/Basketbroom/Content/Art/Characters` remain
project assets. No stock package was downloaded or copied from Hogwarts Legacy.
This document makes no independent license or redistribution claim.

Three serialized strings in the installed body Control Rig name unavailable
`/Game/Developers/Jeremie/MetaHuman/` packages. A string scan cannot establish
whether those are live dependencies. The tool reports them, copies none of them,
and checks actual Asset Registry hard dependencies after the stock files are
staged. Any unstaged `/Game` hard dependency stops authoring. The actual first
staging pass satisfied that hard-dependency check and loaded the mesh/skeleton;
the three text references remain reported rather than treated as imported files.

The generated asset is:

`/Basketbroom/Art/Characters/A_BB_SeatedFlight_Quinn`

Its pose is authored for Basketbroom, using the stock skeleton's measured limb
lengths. It faces +X, places the pelvis near the existing broom seat, leans the
torso forward, bends both knees with the feet below the seat, and reaches both
hands toward the grip. A two-second, 30 FPS loop adds restrained torso/head
movement while solving the hands back toward fixed targets. It does not reuse
the template's standing, falling, weapon or walking animation as flight.

The root transform remains constant across the loop and root motion is disabled.
No skeleton reference pose or bone lengths are edited. A raised, 34 cm transverse
leather grip at local x=43, z=7 cm and a 15.5 cm wood stem support the hands at
their observed posed positions. The first side render exposed the gap above the
straight broom shaft; the raised support was added and reviewed in all three
views. Exact finger curls/palm contact, banking and catch/throw/stun animation
still need authored detail. A maximum 5.30 cm difference from the original hand
IK targets is reported; the support uses the resulting hand positions.

## Usage and guards

- `inspect()` is read-only and runs in ordinary Python. Running the file as a
  script calls only this inventory function.
- `build()` explicitly copies the bounded stock packages and authors the named
  animation. It requires the exact BasketbroomDev project, UE5.8 and stopped PIE.
- `build(replace_generated=True)` may replace only an animation carrying this
  generator's metadata. It cannot replace an unrelated hand-authored animation.
- Only the generated animation and four team instances are saved through Unreal.
  The staging tool does not save maps, stage actors, change project settings or
  touch unrelated dirty assets.

For a fresh checkout, install the UE5.8 Third Person template/shared character
content and open `DevelopmentHarness/BasketbroomDev.uproject`. With PIE stopped,
run the tool through the editor bridge using script `stage_skeletal_rider.py` and
arguments `{"operation":"build","replace_generated":true}`. That reconstructs
the bounded local stock packages and regenerates only this tool's own animation
and material outputs. An empty argument object defaults to a compact read-only
inventory. No files are imported merely by importing the Python module.
Restart the editor after restoring stock assets in a fresh checkout: native
constructor asset finders may already have cached missing assets for that session.

The implementation uses reflected APIs verified against local UE5.8 headers:
`AnimPoseExtensions.get_reference_pose`, `get_bone_pose`, `set_bone_pose`,
`AnimSequenceFactory`, and the animation's read-only controller reference with
`add_bone_curve` and `set_bone_track_keys`. These APIs allow authoring a baked
animation without a runtime Control Rig graph. Epic documents the underlying
[animation data controller](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/IAnimationDataController).

Python syntax, actual stock package loading, 161 bone tracks with 61 keys each,
finite transforms, root stability, loop continuity and an evaluated animation
pose passed. Both knees bend approximately 99.2 degrees. The preview's actual
skeletal component reported pelvis world z=1408.23 and foot z=1346.37 when spawned
at z=1400, confirming that the component evaluated the seated pose rather than
showing a reference mannequin.

The first execution removed a non-reflected `notify_populated` call; the factory
already initializes/notifies the animation model. The UE5.8 material vector
setter also returns false unconditionally in its local C++ implementation, so
the authoring tool verifies material values with getters instead. These were
authoring API issues, not native gameplay failures.

## Native integration and observed evidence

The native source now uses the existing Character mesh for the skeletal body and
remote movement smoothing. The broom and third-person Hurley remain attached
there. The animation already fits +X and the current component origin;
do not apply a conventional standing-mannequin -90 degree yaw/-90 cm offset to
that parent, which would also move existing equipment.

The primitive body is replaced when all six required mesh/animation/material
assets load. Missing prerequisites retain the primitive fallback. The body uses
NoCollision and OwnerNoSee; existing cockpit equipment is unchanged. Team
material changes follow the existing replicated team field. The capsule, flight
movement, network ownership and simulation are unchanged in source. Animation
update-rate optimization is enabled, but its performance has not been measured.

On September 12, `.local/native-rider-art-inspection.json` reported **16/16**
riders valid, with eight Teal and eight Copper. Every rider had the expected
Quinn mesh, original animation, looping single-node playback configuration,
disabled root motion, NoCollision, owner filtering, correct team materials and
raised hand support. No legacy primitive body pieces remained on those riders.
This is configuration evidence from one native PIE world; a single read does
not establish animation advancement or network transport.

The reviewed [native flight capture](Screenshots/native-flight.png) is an actual
1600×900 native PIE viewport image from a practice session, with the clock at
02:59, Scout controls and equipment HUD visible. It shows seated remote riders
and the local cockpit without the owner's body obstructing that view. The
closer asset views below establish the seated silhouette, grip support and team
surface appearance. These images cover the observed viewpoints, not every
owner/remote combination or distant LOD.

Sustained animation playback, finger contact, banking and action animation,
distant LODs, packaged character rendering and visual network smoothing still
need focused review. Frame time has not been measured. The stock mannequin's
body design remains recognizable and needs an original sporting-character art
pass.

## Repeating the real asset renders

With PIE stopped, send `preview_skeletal_rider.py` through the bridge with
`{"operation":"start","team":"Teal"}` or `Copper`. It returns immediately;
read `.local/skeletal-rider-preview.json` for completion and the three PNG paths.
The successful runs took 9.015 and 9.016 seconds. The reviewed Teal views are in
`.local/art-review/skeletal-rider/1789217150730916000/`; Copper views are in
`.local/art-review/skeletal-rider/1789217270397625800/`.

The helper spawns only transient editor preview actors and destroys them after
capture, restores the prior viewport/selection, and releases its render target.
It saves no map. Transient actor operations can still mark the editor map dirty;
there are no intended map changes to save. The original dirty flag was not
recorded during these review runs.

The reliable capture path uses a transient `SceneCapture2D`, a 1280×960 RGBA8
render target, `SCS_FINAL_COLOR_LDR`, disabled automatic capture, and persistent
rendering state. Eight Slate frames warm the capture before
`RenderingLibrary.export_render_target` writes the PNG. This works without an
active viewport. The PNG validator walks chunks because Unreal's render-target
export can include zero padding after the IEND chunk.

For skeletal assets specifically, `override_animation_data` immediately ticks
animation and refreshes the component's bones. `play_animation` followed by
`set_position` alone left the idle editor preview in reference pose. The helper
checks the component's pelvis/foot positions before rendering. Asset preview
lighting is not a measurement of the packaged gameplay viewport's appearance.

To repeat the native configuration check, run `probe_native_rider_art.py` through the
bridge with a label such as `{"label":"combined-native-rider"}` while native
BB_Regulation PIE is running. It reads all 16 riders and checks mesh/animation
paths, looping single-node configuration, root-motion setting, NoCollision,
owner filtering, team material paths, raised support and absence of legacy body
pieces. It writes `.local/native-rider-art-inspection.json`; the actual combined
native run passed 16/16 at 13:08:04 UTC on September 12. It does not change roles,
input, rule state, transforms, animation state or assets.

The final review session ended with PIE stopped, the unsaved editor review
fixtures discarded when the editor closed, and the previous Standalone play
mode restored. No preview camera or intended map edit belongs in the saved map.
