# Human athlete authoring checkpoint

The character lab is isolated at `.local/CharacterLab/BasketbroomCharacterLab.uproject`.
It uses the installed Unreal 5.8 MetaHuman Creator and its optional source data.
The main prototype and native Hogwarts Creator Kit remain separate projects.
The tools below do not copy Hogwarts assets into the Unreal prototype.

## Owned designs and assemblies

`Tools/stage_human_players.py` inspects or creates two independently owned adult
designs from the installed Ada and Omari presets. The design assets are
`/Game/BasketbroomHumans/Design/BB_AthleteA` and `BB_AthleteB`.
Existing unrelated assets are refused. Creation does not request cloud services.

`Tools/build_human_players.py` supports these explicit bridge operations:

- `inspect`: read character and current observer state.
- `prepare`: preserve preset hair/other slots, select the installed garment,
  and set the actual shirt color. A defaults to mint and B to copper for review;
  runtime appearance identity and team color remain separate concerns.
- `request`: request joints-only facial rigging and source textures. Epic may
  require user authentication. Requests are nonblocking and retain their edit
  session while a slate observer checks `can_build_meta_human`.
- `resume`: continue observing the same retained requests after a timeout;
  it does not submit requests again.
- `assemble`: create a new Optimized Medium actor under
  `/Game/BasketbroomHumans/Assembled/<name>`, sharing the owned `Common` folder.
- `checkpoint_existing`: finish checkpointing a saved assembly identified by its
  exact prior receipt, without rebuilding or deleting its outputs.

Mutations require the lab project, stopped Play, owned designs and clean existing
work. Exact design backups are hash-verified. Shared assembly assets have a saved
hash manifest and are backed up before a subsequent athlete assembly. Outputs are
batch-saved only after checking the generated Blueprint, its Medium export tag,
and skeletal meshes. `.local/CharacterLab/assembly-manifest.json` records durable
assemblies; local receipts retain individual operations and failures.

Both designs and their Medium assemblies have been saved. This does not by itself
establish completed game integration, a finished flight outfit, or packaged QA.
The default installed wardrobe is a shirt and shorts. Root-owned flight/uniform
tools add the seated animation and garment-only team materials separately.

## Verified engine behavior and recovery

Cloud callbacks require the design's edit session to stay registered. A timeout
therefore leaves it alive and reports attention required. A failed or timed-out
request is never described as cancelled. Closing an asset editor can finish on a
later slate tick; if the close guard refuses a new operation, wait for that exact
owned window to disappear before retrying.

`MetaHumanDefaultEditorPipelineBase.cpp` explicitly removes the pre-baked groom
intermediates from AssetRegistry and clears their Public/Standalone flags after
their results are baked into exported face maps. The four `T_PreBakedGroom_`
packages for Color/NSR at LOD3/LOD5to7 can remain dirty until a later tick. They
are not exported assets. The tool verifies their exact names and absence from
registry/referencers, then uses normal engine garbage collection; it never
restores flags or saves discarded intermediates. Deferred cleanup is recorded.

An initial final design-thumbnail save surfaced an ARKit control-rig skeleton
identity error after the actual A assembly outputs had already saved. Recovery
confirmed a compiled Medium Blueprint and complete files, collected discarded
intermediates and wrote the manifest. Future assembly skips a clean design save.
Facial animation still requires actual render and packaged validation.

B's first assembly exhausted Windows commit capacity. A fresh lab process
completed it. Save checkpoints and restart the lab between heavy character
operations when needed; these tools do not change Windows memory settings.

## Geometry, render and migration probes

`Tools/probe_human_players.py` records actual hard/soft package dependencies,
local files and hashes, external roots, body texture resolutions, material
parameters, skeletal/animation bindings and LODs. Component inspection spawns one
transient owned actor, destroys it and restores selection, without saving a map.
Its dependency graph is an inventory, not an automatic migration allowlist.

A's inspected assembly has 272 local packages with no missing package files:
252 hard-reachable and 20 reachable only through soft references. Its Body and
Face each have three LODs; its garment has four and follows Body. Face retains
the actual `ABP_Face` and face post-process pipeline. The inspected body/chest
basecolor, normal and cavity textures are 2048 square.

The first editor capture evaluated the seated Body but left Face in its standing
reference pose, placing the head outside the original camera framing. This was
fixed in the transient preview by resetting Face's existing animation class after
Body's pose evaluates. Face and Body now report matching head positions. A's
`renders/1790335091596773900/three-quarter.png` and B's
`renders/1790335143930229400/front.png` were visually inspected. The actual face
AnimBP and post-process pipeline remain intact. Runtime/packaged facial behavior
still needs its own verification.

`Tools/probe_human_flightwear.py` verified intact source-body access.
The MetaHuman subsystem's transient preview actor is initialized from its intact
CharacterData body before the assembly pipeline prunes covered faces. The probe
copies preview and assembled meshes into transient GeometryScript DynamicMeshes,
records topology/UV/skinning contracts, then closes only its owned preview state.
Receipt `flightwear-probes/20260925-112120-889591-a26c765c/result.json` recorded
60,816 intact preview triangles versus 11,843 pruned assembly triangles, one UV
channel, valid sampled skin weights, unchanged saved asset bytes and no dirty
packages.

`Tools/stage_human_flightwear.py` uses this source for a new garment. Its `inspect`
operation fits transient long sleeves, a jacket and trousers, with separate
original boot shells fitted around the actual feet. The cloth retains its UVs
and sampled skin weights; new boots receive nearest-surface source weights.
`build` exports one new mesh, team materials and a dedicated skeleton under
`/Game/BasketbroomHumans/Flightwear/<name>`. Existing output is refused. It does
not edit original assemblies or automatically activate the outfit in gameplay.
R1 was rendered and rejected: unbounded wrist planes removed the knees, material
IDs followed irregular triangle edges, and the boots were too bulky. The generator
staged new `Flightwear/<name>/r2` packages, retaining all R1 assets. R2
bounds cuff operations to the arm region, asserts continuous trouser coverage,
projects opening rims to their hem planes, uses continuous pre-skinned panel masks,
and measures narrower boot cross sections in the actual foot orientation. Offline
checks preserve every central-leg triangle in 40–90 cm and enclose every sampled
source foot/lower-leg vertex within the revised boot shell. A's R2 renders at
`renders/1790339762994606600` confirmed full trousers and slimmer boots. Jagged
dark marks on the hip and forearm disappeared in the same-pose no-shadow render
`renders/1790340166724729300/side.png`: these were cast shadows, not cloth cracks
or material bands. The normal preview keeps shadows enabled.

R2's wide neckline remains a geometry limitation: the source Body's 92-vertex
chest rim dips from Z144 to Z134.6 cm, leaving part of genuine Face's lower chest
exposed. The generator now defaults to separate `Flightwear/<name>/r3` packages.
R3 keeps the lower-body/arm fit, restores 20 top-of-Body triangles, and fits a low
chest/standing-collar band from the same owned transient Face. It validates matching
chest rims, overlaps the jacket, and transfers Body weights to the new cloth band;
the actual Face, its weights and skin material remain untouched. Unexpected rim
geometry or retained facial skeleton bones aborts before saving. Offline validation
used actual Body geometry and a synthetic neck-band fixture. Both actual R3 builds
and three-view lab captures now pass authoring review: A mint at
`renders/1790341228556516500`, B copper at `renders/1790341304263183900`.
The neckline and full trousers remain covered in the evaluated flight pose.
These are one-LOD human outfit
baselines, not final detailed wardrobe assets.
`api` reports installed reflected method contracts without fitting or saving.

`Tools/stage_human_cosmetics.py` creates a new cosmetic Blueprint by duplicating
the owned assembly and editing only the duplicate's clothing template. It replaces
the complete override-material array, compiles, then spawns a transient actor to
check that construction retained the new mesh and its Body leader. Bone names,
sampled follower transforms and all other Body/Face/groom/LODSync contracts are
checked before saving. It defaults to R3 under `Cosmetics/<name>/r3`, also allows
explicit R2, and refuses the visually rejected R1. Its receipt supplies exact runtime garment bindings and
dependency roots. `inventory` reads the existing cosmetic output without editing it.
`recover` validates an already saved owned output against the same metadata,
template and live actor contracts, then writes its missing receipt without editing
or resaving the Blueprint. UE FNames compare case-insensitively; component
transforms and LODSync use numeric/enum values rather than wrapper addresses.

`create_new_skeletal_mesh_asset_from_mesh` calls
`MergeAllBonesToBoneTree`, so it must receive a dedicated owned skeleton duplicate
to preserve the original human skeleton. Face, skin, body proportions and original
assembled assets should remain unchanged by garment fitting.

## Migration and optional runtime activation

`Tools/plan_human_migration.py` runs outside Unreal. It reads both saved assembly
inventories, verifies source hashes, checks target collisions, resolves installed
plugin/module descriptor ownership and writes `.local/CharacterLab/migration-plan.json`.
It copies no assets. Package paths remain `/Game/BasketbroomHumans/...`; any future
copy belongs under `DevelopmentHarness/Content/BasketbroomHumans`, not a different
mount that would break serialized references. Shared preview references can reach
the other owned athlete and must remain explicit in the dependency graph.

The current inventories do not expose package flags through Python. The offline
planner instead reads the installed UE5.8 binary package-summary format, verifying
the format version, package name and header bounds before reading `PKG_EditorOnly`.
Other versions stay unresolved. No inventoried local package has that flag, but
this alone does not establish cook compatibility: a dependency list is not a cook allowlist.
New flightwear, animation and both team-material roots need a combined inventory
after a new cosmetic actor variant is authored. Do not overwrite the saved
assembly Blueprint to make that variant.

Runtime already accepts `FBBHumanRiderVariant` through
`ABBRiderCharacter::ConfigureHumanCosmetics`. Each variant supplies an actor class,
verified Body name, fitted animation, alignment transform and garment slot/material
bindings. There is currently no garment-mesh override, so the cosmetic actor must
already contain its accepted outfit. `UBBHumanRiderRoster` now supplies a read-only
variant array. The rider's optional `HumanRoster` Game-config soft reference is
resolved once at BeginPlay when no explicit variants were supplied; Unreal reuses
the loaded object, retained by a transient strong reference. Dedicated servers skip
this presentation load. No path is configured yet. A staged roster needs an explicit
cook rule. Empty/missing/invalid configuration keeps the current fallback.
Appearance identity remains independent of team; team colors apply only to garment
bindings. The source implementation compiled successfully; configured-asset runtime
checks remain pending.
the offline planner neither configures nor activates it.

The combined R3 inventory on September 25 contains 380 saved runtime packages
(508,473,539 bytes), with no missing files or unresolved registry queries. These
were exclusively copied to `DevelopmentHarness/Content/BasketbroomHumans` with
SHA-256 verification; source assets and existing target files were preserved.
The largest package is 51,187,816 bytes, below GitHub's individual file limit.
Saved asset paths resolve ten required runtime/content plugins and AnimationData
for Editor only. The native editor build with those plugins passed.

The saved mesh inventory exposed no AssetGuideline records. Renderer settings
therefore follow the installed MetaHuman SDK's `MetaHumanValidationTests.cpp`
(lines 1609–1653): 16-bit bone indices, unlimited influences, compiled skin cache,
vertex-color tangent blending 2 and experimental skeletal chunking 1. This does
not change the project's RHI or assume a ray-tracing requirement.

Main-project loading succeeds. Roster staging and gameplay acceptance are still
in progress; the accepted desktop package remains the tested Quinn/trails build.
