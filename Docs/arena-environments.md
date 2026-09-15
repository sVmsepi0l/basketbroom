# Two arena environments

The standalone UE5.8 regulation game now has source and a bounded staging path for two original arena settings. Saved-map and playable acceptance are recorded separately below; procedural source generation alone is not a claim of finished art or native Hogwarts match integration.

## Four Corners red rock

`/Basketbroom/Maps/BB_Redrock` places the existing arena inside a huge, open-front sandstone alcove. Seven three-dimensional sediment beds wrap its sides and back. A closed, sculpted sandstone cap projects over the arena, with its soffit above the complete pyramidion roof. A terraced village uses Puebloan-inspired adobe rooms, stepped roof coping, round lookout towers, recessed dark doors/windows, projecting timber vigas and roof-access ladders. Talus, sagebrush and distant mesas extend the setting beyond the competition enclosure.

The architecture is original scenery inspired by the user's Cliff Palace/Mesa Verde direction, not a reconstruction of a specific historic site. Warm stone, amber daylight and a blue sky support the red-rock palette from the approved promotional art.

## Coastal old-growth redwoods

`/Basketbroom/Maps/BB_Redwoods` opens toward an actual sea surface and receding basalt stacks, with a grove around the back and sides. Three original redwood variants have tapering fluted boles, buttress roots, asymmetric woody branches and multiple tiers of solid geometric needle clusters. Shared source meshes form 49 varied trees. A mossy bluff, sword-fern understory, fallen giant, ocean wave displacement and geometric breaker crests carry the coastal setting through the playable view.

The open side faces the Pacific-inspired horizon, with cool daylight and restrained blue-green haze. This is a fictional venue drawing on northern California and southern Oregon old growth, not an exact mapped location.

## Source, scope and preservation

`Tools/build_arena_environments.py --generate` creates deterministic, original OBJ geometry and `SourceArt/Environments/environments_manifest.json`, using centimetres and Z up. It does not call Unreal or modify existing arena source meshes. Red rock uses 16 meshes and 72,144 source triangles. Redwoods use 14 meshes and 243,518 source triangles, with approximately 2.77 million instance triangles before engine culling. All 30 OBJ files together are approximately 21.4 MB; no single file exceeds 3.2 MB.

The source checker tests each transformed triangle against a conservative rectangular protected volume. Its sides extend 150 cm beyond the current arena and its top is 250 cm above the 7,141.257 cm pyramidion apex. All 2,844,466 instance triangles passed without a decorative intrusion. The actual pyramid-shaped playing volume is wholly contained by that protected box.

The two variants retain the exact 45%-expanded enclosure, all eight hoop sizes/heights/placements, rebound geometry, floor, spectator stands, scoring actors, native game mode and sporting distances. Only environment actors use the `BB.Environment.v1` tag, and their primitive components use `NoCollision` with overlap events disabled. Scenery cannot change ball rebounds, catching, player bounds or referee marks. The stage verifies ordinary arena collision again after map saving/reloading.

The original surface inputs are `T_BB_RedSandstone_Albedo.png`, `T_BB_Adobe_Albedo.png` and `T_BB_RedwoodBark_Albedo.png` under `SourceArt/Environments/Textures`. These are generated base-color art, not calibrated photogrammetry or complete physically based texture sets. Materials use world-space triplanar projection with restrained tints and roughness, preserving physical detail size on large surfaces and differently scaled instances. Foliage is geometry rather than translucent cards, and the sea has low-amplitude real vertex movement.

## Staging and verification

Run the editor bridge with `stage_arena_environments.py` and `{"dry_run": true}`, then `{"dry_run": false}`. The helper only accepts the owned UE5.8 DevelopmentHarness project and a clean, stopped editor. The source map is `/Basketbroom/Maps/BB_Regulation`; it is never overwritten. New variants are made with `NewLevelFromTemplate`.

Before mutation, the helper checks all source hashes, exact destination ownership and current enclosure dimensions. Existing destination packages are backed up to an immutable `.local/environment-stage/<attempt>/backups` folder. It then imports only the original environment assets and replaces exactly nine old, verified background/light actors in the duplicated maps. An actor label alone never grants ownership. Every other actor's identity, class, component settings, material references and transform must match the source map.

After authoring, the helper verifies no environment collision, runs actual enclosure/goal collision checks before save and after reload, confirms the native regulation game mode and restores the original map. A complete content hash comparison rejects saved changes outside the exact map/mesh/material/texture allowlist. Re-running the stage replaces only the same owned environment actors and assets; unexpected sporting differences cause a failure rather than an overwrite. Receipts never claim gameplay tests that were not run.

Thirteen offline tests currently pass: source hashes/current dimensions, rotated and scaled placement, outward surface winding, triangle crossing with all vertices outside the box, valid overhang clearance, rejection of intruding scenery, exact package allowlist, false backdrop ownership, and rejection of changed or missing sporting actors/materials/transforms.

Saved UE5 maps, live gameplay, packaged map selection and visual review remain pending until the root staging and verification run records their receipts here. The native Creator Kit must import these original sources separately through its supported engine. UE5 `.uasset` files are never a native port mechanism, and no native map registration, entrance, dungeon return or full match integration is claimed by this environment source stage.


## September 15 staging checkpoint

The first UE5 stage saved all 54 allowed packages and preserved source content. Receipt: `.local/environment-stage/20260915-131953-509706-d0c0c143/result.json`; SHA-256 `2ab5c68fd57b1be1408a5b2688f6b42126e75b5a599d963457e34fa46bc8927e`. Root reported a visual defect: front-facing cameras see the cliff rear, indicating possible OBJ Y-axis reflection. This is unresolved at checkpoint and the venue art is not visually accepted.

`Tools/repair_arena_environment_axes.py` defaults to a read-only imported-bounds/topology audit. It compares all 30 actual static-mesh signed bounds and triangle counts against exact source manifests, requires one consistent handedness across asymmetric meshes, and rejects unexplained transforms. If Y reflection is proved, execution compensates only each owned environment mesh actor's Y scale, preserving positions, rotations, all sporting actors and every mesh/material asset. It backs up, saves/reloads and checks both maps. It does not rotate cameras to conceal incorrect geometry. The diagnostic/repair has compiled but has not been run at this checkpoint. Its report explicitly distinguishes signed-bound proof from a full vertex-by-vertex export comparison.

The native broom helper `Tools/test_hlck_native_broom.py` also exists: read-only preflight by default; explicit execution activates only the witnessed house-broom inventory record, confirms the real native returned tool and local controller possession of a FlyingBroom, observes flight, and normally dismounts/restores initial tools. Ascent and end-PIE are separate explicit options. Only captured native APIs are used; no native flight result is claimed yet. `{"operation":"inspect"}` reports an existing observer; `{"operation":"cancel"}` cancels pre-activation observation or requests normal cleanup for an activated test.
