# two arena environments

the standalone UE5.8 regulation game now has source and a bounded staging path for two original arena settings. saved-map and playable acceptance are recorded separately below; procedural source generation alone is not a claim of finished art or native hogwarts match integration.

## four corners red rock

`/Basketbroom/Maps/BB_Redrock` places the existing arena inside a huge, open-front sandstone alcove. seven three-dimensional sediment beds wrap its sides and back. a closed, sculpted sandstone cap projects over the arena, with its soffit above the complete pyramidion roof. a terraced village uses puebloan-inspired adobe rooms, stepped roof coping, round lookout towers, recessed dark doors/windows, projecting timber vigas and roof-access ladders. talus, sagebrush and distant mesas extend the setting beyond the competition enclosure.

the architecture is original scenery inspired by the user's cliff Palace/Mesa verde direction, not a reconstruction of a specific historic site. warm stone, amber daylight and a blue sky support the red-rock palette from the approved promotional art.

## coastal old-growth redwoods

`/Basketbroom/Maps/BB_Redwoods` opens toward an actual sea surface and receding basalt stacks, with a grove around the back and sides. three original redwood variants have tapering fluted boles, buttress roots, asymmetric woody branches and multiple tiers of solid geometric needle clusters. shared source meshes form 49 varied trees. a mossy bluff, sword-fern understory, fallen giant, ocean wave displacement and geometric breaker crests carry the coastal setting through the playable view.

the open side faces the pacific-inspired horizon, with cool daylight and restrained blue-green haze. this is a fictional venue drawing on northern california and southern oregon old growth, not an exact mapped location.

## source, scope and preservation

`Tools/build_arena_environments.py --generate` creates deterministic, original obj geometry and `SourceArt/Environments/environments_manifest.json`, using centimetres and z up. it does not call unreal or modify existing arena source meshes. red rock uses 16 meshes and 72,144 source triangles. redwoods use 14 meshes and 243,518 source triangles, with approximately 2.77 million instance triangles before engine culling. all 30 obj files together are approximately 21.4 mb; no single file exceeds 3.2 MB.

the source checker tests each transformed triangle against a conservative rectangular protected volume. its sides extend 150 cm beyond the current arena and its top is 250 cm above the 7,141.257 cm pyramidion apex. all 2,844,466 instance triangles passed without a decorative intrusion. the actual pyramid-shaped playing volume is wholly contained by that protected box.

the two variants retain the exact 45%-expanded enclosure, all eight hoop sizes/heights/placements, rebound geometry, floor, spectator stands, scoring actors, native game mode and sporting distances. only environment actors use the `BB.Environment.v1` tag, and their primitive components use `nocollision` with overlap events disabled. scenery cannot change ball rebounds, catching, player bounds or referee marks. the stage verifies ordinary arena collision again after map saving/reloading.

the original surface inputs are `T_BB_RedSandstone_Albedo.png`, `T_BB_Adobe_Albedo.png` and `T_BB_RedwoodBark_Albedo.png` under `SourceArt/Environments/Textures`. these are generated base-color art, not calibrated photogrammetry or complete physically based texture sets. materials use world-space triplanar projection with restrained tints and roughness, preserving physical detail size on large surfaces and differently scaled instances. foliage is geometry rather than translucent cards, and the sea has low-amplitude real vertex movement.

## staging and verification

run the editor bridge with `stage_arena_environments.py` and `{"dry_run": true}`, then `{"dry_run": false}`. the helper only accepts the owned UE5.8 developmentharness project and a clean, stopped editor. the source map is `/Basketbroom/Maps/BB_Regulation`; it is never overwritten. new variants are made with `NewLevelFromTemplate`.

before mutation, the helper checks all source hashes, exact destination ownership and current enclosure dimensions. existing destination packages are backed up to an immutable `.local/environment-stage/<attempt>/backups` folder. it then imports only the original environment assets and replaces exactly nine old, verified background/light actors in the duplicated maps. an actor label alone never grants ownership. every other actor's identity, class, component settings, material references and transform must match the source map.

after authoring, the helper verifies no environment collision, runs actual enclosure/goal collision checks before save and after reload, confirms the native regulation game mode and restores the original map. a complete content hash comparison rejects saved changes outside the exact map/mesh/material/texture allowlist. re-running the stage replaces only the same owned environment actors and assets; unexpected sporting differences cause a failure rather than an overwrite. receipts never claim gameplay tests that were not run.

thirteen offline tests currently pass: source hashes/current dimensions, rotated and scaled placement, outward surface winding, triangle crossing with all vertices outside the box, valid overhang clearance, rejection of intruding scenery, exact package allowlist, false backdrop ownership, and rejection of changed or missing sporting actors/materials/transforms.

saved ue5 maps, live gameplay, packaged map selection and visual review remain pending until the root staging and verification run records their receipts here. the native creator kit must import these original sources separately through its supported engine. ue5 `.uasset` files are never a native port mechanism, and no native map registration, entrance, dungeon return or full match integration is claimed by this environment source stage.


## september 15 staging checkpoint

the first ue5 stage saved all 54 allowed packages and preserved source content. Receipt: `.local/environment-stage/20260915-131953-509706-d0c0c143/result.json`; sha-256 `2ab5c68fd57b1be1408a5b2688f6b42126e75b5a599d963457e34fa46bc8927e`. root reported a visual defect: front-facing cameras see the cliff rear, indicating possible obj y-axis reflection. this is unresolved at checkpoint and the venue art is not visually accepted.

`Tools/repair_arena_environment_axes.py` defaults to a read-only imported-bounds/topology audit. it compares all 30 actual static-mesh signed bounds and triangle counts against exact source manifests, requires one consistent handedness across asymmetric meshes, and rejects unexplained transforms. if y reflection is proved, execution compensates only each owned environment mesh actor's y scale, preserving positions, rotations, all sporting actors and every mesh/material asset. it backs up, saves/reloads and checks both maps. it does not rotate cameras to conceal incorrect geometry. the diagnostic/repair has compiled but has not been run at this checkpoint. its report explicitly distinguishes signed-bound proof from a full vertex-by-vertex export comparison.

the native broom helper `Tools/test_hlck_native_broom.py` also exists: read-only preflight by default; explicit execution activates only the witnessed house-broom inventory record, confirms the real native returned tool and local controller possession of a flyingbroom, observes flight, and normally dismounts/restores initial tools. ascent and end-pie are separate explicit options. only captured native apis are used; no native flight result is claimed yet. `{"operation":"inspect"}` reports an existing observer; `{"operation":"cancel"}` cancels pre-activation observation or requests normal cleanup for an activated test.
