# skeletal rider authoring checkpoint

`Tools/stage_skeletal_rider.py` ran in UE5.8.1 on september 12, 2026. it staged the
installed stock dependencies and saved an original seated animation plus four
derived team material instances. real front, side and three-quarter asset renders
were reviewed, the combined native c++ build succeeded, and the read-only native
pie rider probe passed for all 16 riders. the final native gameplay capture shows
seated team-colored riders in the arena. this is a stock-character foundation,
not finished character art or an aaa graphics milestone.

## exact source and output

the source is the locally installed epic UE5.8 third person shared character
content at:

`C:\Program Files\Epic Games\UE_5.8\Templates\TemplateResources\High\Characters\Content\Mannequins`

the selected mesh is `Meshes/SKM_Quinn_Simple.uasset`; the shared skeleton is
`Meshes/SK_Mannequin.uasset`. a conservative scan of serialized package names
finds 23 installed packages totaling 81,908,625 bytes (about 78.1 MiB). that set
includes manny simple, both characters' materials/textures, the shared physics
asset and body control Rig. the skeleton's preview references pull in both
meshes; copying only quinn's mesh would leave references unresolved.

the explicit `build()` preserves their original
`/Game/Characters/Mannequins/` package paths in this ue5 project's content folder.
it refuses to overwrite a differing local package. this is epic stock content,
not original basketbroom geometry and not hogwarts legacy content. the derived
team materials apply teal or copper paint, roughness 0.68 and metallic 0.18 to
the paint layer while preserving the stock surface maps. the stock ue logo
switch is disabled in these four derived instances.

the stock directory `DevelopmentHarness/Content/Characters/Mannequins` is a local
installed-template dependency, intended to be reconstructed rather than checked
into this repository. the generated animation and four owned material instances
under `DevelopmentHarness/Plugins/Basketbroom/Content/Art/Characters` remain
project assets. no stock package was downloaded or copied from hogwarts Legacy.
this document makes no independent license or redistribution claim.

three serialized strings in the installed body control rig name unavailable
`/Game/Developers/Jeremie/MetaHuman/` packages. a string scan cannot establish
whether those are live dependencies. the tool reports them, copies none of them,
and checks actual asset registry hard dependencies after the stock files are
staged. any unstaged `/Game` hard dependency stops authoring. the actual first
staging pass satisfied that hard-dependency check and loaded the mesh/skeleton;
the three text references remain reported rather than treated as imported files.

the generated asset is:

`/Basketbroom/Art/Characters/A_BB_SeatedFlight_Quinn`

its pose is authored for basketbroom, using the stock skeleton's measured limb
lengths. it faces +x, places the pelvis near the existing broom seat, leans the
torso forward, bends both knees with the feet below the seat, and reaches both
hands toward the grip. a two-second, 30 fps loop adds restrained torso/head
movement while solving the hands back toward fixed targets. it does not reuse
the template's standing, falling, weapon or walking animation as flight.

the root transform remains constant across the loop and root motion is disabled.
no skeleton reference pose or bone lengths are edited. a raised, 34 cm transverse
leather grip at local x=43, z=7 cm and a 15.5 cm wood stem support the hands at
their observed posed positions. the first side render exposed the gap above the
straight broom shaft; the raised support was added and reviewed in all three
views. exact finger curls/palm contact, banking and catch/throw/stun animation
still need authored detail. a maximum 5.30 cm difference from the original hand
ik targets is reported; the support uses the resulting hand positions.

## usage and guards

- `inspect()` is read-only and runs in ordinary Python. running the file as a
  script calls only this inventory function.
- `build()` explicitly copies the bounded stock packages and authors the named
  animation. it requires the exact basketbroomdev project, UE5.8 and stopped PIE.
- `build(replace_generated=true)` may replace only an animation carrying this
  generator's metadata. it cannot replace an unrelated hand-authored animation.
- only the generated animation and four team instances are saved through Unreal.
  the staging tool does not save maps, stage actors, change project settings or
  touch unrelated dirty assets.

for a fresh checkout, install the UE5.8 third person template/shared character
content and open `DevelopmentHarness/BasketbroomDev.uproject`. with pie stopped,
run the tool through the editor bridge using script `stage_skeletal_rider.py` and
arguments `{"operation":"build","replace_generated":true}`. that reconstructs
the bounded local stock packages and regenerates only this tool's own animation
and material outputs. an empty argument object defaults to a compact read-only
inventory. no files are imported merely by importing the python module.
restart the editor after restoring stock assets in a fresh checkout: native
constructor asset finders may already have cached missing assets for that session.

the implementation uses reflected apis verified against local UE5.8 headers:
`AnimPoseExtensions.get_reference_pose`, `get_bone_pose`, `set_bone_pose`,
`animsequencefactory`, and the animation's read-only controller reference with
`add_bone_curve` and `set_bone_track_keys`. these apis allow authoring a baked
animation without a runtime control rig graph. epic documents the underlying
[animation data controller](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/IAnimationDataController).

python syntax, actual stock package loading, 161 bone tracks with 61 keys each,
finite transforms, root stability, loop continuity and an evaluated animation
pose passed. both knees bend approximately 99.2 degrees. the preview's actual
skeletal component reported pelvis world z=1408.23 and foot z=1346.37 when spawned
at z=1400, confirming that the component evaluated the seated pose rather than
showing a reference mannequin.

the first execution removed a non-reflected `notify_populated` call; the factory
already initializes/notifies the animation model. the UE5.8 material vector
setter also returns false unconditionally in its local c++ implementation, so
the authoring tool verifies material values with getters instead. these were
authoring api issues, not native gameplay failures.

## native integration and observed evidence

the native source now uses the existing character mesh for the skeletal body and
remote movement smoothing. the broom and third-person hurley remain attached
there. the animation already fits +x and the current component origin;
do not apply a conventional standing-mannequin -90 degree yaw/-90 cm offset to
that parent, which would also move existing equipment.

the primitive body is replaced when all six required mesh/animation/material
assets load. missing prerequisites retain the primitive fallback. the body uses
nocollision and ownernosee; existing cockpit equipment is unchanged. team
material changes follow the existing replicated team field. the capsule, flight
movement, network ownership and simulation are unchanged in source. animation
update-rate optimization is enabled, but its performance has not been measured.

on september 12, `.local/native-rider-art-inspection.json` reported **16/16**
riders valid, with eight teal and eight Copper. every rider had the expected
quinn mesh, original animation, looping single-node playback configuration,
disabled root motion, nocollision, owner filtering, correct team materials and
raised hand support. no legacy primitive body pieces remained on those riders.
this is configuration evidence from one native pie world; a single read does
not establish animation advancement or network transport.

the reviewed [native flight capture](Screenshots/native-flight.png) is an actual
1600×900 native pie viewport image from a practice session, with the clock at
02:59, scout controls and equipment hud visible. it shows seated remote riders
and the local cockpit without the owner's body obstructing that view. the
closer asset views below establish the seated silhouette, grip support and team
surface appearance. these images cover the observed viewpoints, not every
owner/remote combination or distant LOD.

sustained animation playback, finger contact, banking and action animation,
distant lods, packaged character rendering and visual network smoothing still
need focused review. frame time has not been measured. the stock mannequin's
body design remains recognizable and needs an original sporting-character art
pass.

## repeating the real asset renders

with pie stopped, send `preview_skeletal_rider.py` through the bridge with
`{"operation":"start","team":"Teal"}` or `Copper`. it returns immediately;
read `.local/skeletal-rider-preview.json` for completion and the three png paths.
the successful runs took 9.015 and 9.016 seconds. the reviewed teal views are in
`.local/art-review/skeletal-rider/1789217150730916000/`; copper views are in
`.local/art-review/skeletal-rider/1789217270397625800/`.

the helper spawns only transient editor preview actors and destroys them after
capture, restores the prior viewport/selection, and releases its render target.
it saves no map. transient actor operations can still mark the editor map dirty;
there are no intended map changes to save. the original dirty flag was not
recorded during these review runs.

the reliable capture path uses a transient `scenecapture2d`, a 1280×960 rgba8
render target, `scs_final_color_ldr`, disabled automatic capture, and persistent
rendering state. eight slate frames warm the capture before
`RenderingLibrary.export_render_target` writes the PNG. this works without an
active viewport. the png validator walks chunks because unreal's render-target
export can include zero padding after the iend chunk.

for skeletal assets specifically, `override_animation_data` immediately ticks
animation and refreshes the component's bones. `play_animation` followed by
`set_position` alone left the idle editor preview in reference pose. the helper
checks the component's pelvis/foot positions before rendering. asset preview
lighting is not a measurement of the packaged gameplay viewport's appearance.

to repeat the native configuration check, run `probe_native_rider_art.py` through the
bridge with a label such as `{"label":"combined-native-rider"}` while native
bb_regulation pie is running. it reads all 16 riders and checks mesh/animation
paths, looping single-node configuration, root-motion setting, nocollision,
owner filtering, team material paths, raised support and absence of legacy body
pieces. it writes `.local/native-rider-art-inspection.json`; the actual combined
native run passed 16/16 at 13:08:04 utc on september 12. it does not change roles,
input, rule state, transforms, animation state or assets.

the final review session ended with pie stopped, the unsaved editor review
fixtures discarded when the editor closed, and the previous standalone play
mode restored. no preview camera or intended map edit belongs in the saved map.
