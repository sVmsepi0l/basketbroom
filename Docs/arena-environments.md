# two arena environments

the standalone UE5.8 regulation game now has source and a bounded staging path for two original arena settings. saved-map and playable acceptance are recorded separately below; procedural source generation alone is not a claim of finished art or native hogwarts match integration.

## four corners red rock

`/Basketbroom/Maps/BB_Redrock` places the existing arena inside a huge, open-front sandstone alcove. seven three-dimensional sediment beds wrap its sides and back. a closed, sculpted sandstone cap projects over the arena, with its soffit above the complete pyramidion roof. a terraced village uses puebloan-inspired adobe rooms, stepped roof coping, round lookout towers, recessed dark doors/windows, projecting timber vigas and roof-access ladders. talus, sagebrush and distant mesas extend the setting beyond the competition enclosure.

the architecture is original scenery inspired by the user's cliff Palace/Mesa verde direction, not a reconstruction of a specific historic site. warm stone, amber daylight and a blue sky support the red-rock palette from the approved promotional art.

## coastal old-growth redwoods

`/Basketbroom/Maps/BB_Redwoods` opens toward an actual sea surface and receding basalt stacks, with a grove around the back and sides. three original redwood variants have tapering fluted boles, buttress roots, asymmetric woody branches and multiple tiers of solid geometric needle clusters. shared source meshes form 49 varied trees: eight selected giants are exactly three times their previous instance size, twenty medium trees are 1.45–1.8 times their previous size, and twenty-one retain their original varied sizes. the giants are interspersed through the near, middle, deep and side groves, keeping different silhouettes and layers visible. a mossy bluff, sword-fern understory, fallen giant, ocean wave displacement and geometric breaker crests carry the coastal setting through the playable view.

the open side faces the pacific-inspired horizon, with cool daylight and restrained blue-green haze. this is a fictional venue drawing on northern california and southern oregon old growth, not an exact mapped location.

## source, scope and preservation

`Tools/build_arena_environments.py --generate` creates deterministic, original obj geometry and `SourceArt/Environments/environments_manifest.json`, using centimetres and z up. it does not call unreal or modify existing arena source meshes. red rock uses 16 meshes and 72,144 source triangles. redwoods use 14 meshes and 243,518 source triangles, with approximately 2.77 million instance triangles before engine culling. all 30 obj files together are approximately 21.4 mb; no single file exceeds 3.2 MB.

the source checker tests each transformed triangle against a conservative rectangular protected volume. its sides extend 150 cm beyond the current arena and its top is 250 cm above the 7,141.257 cm pyramidion apex. all 2,844,466 instance triangles passed without a decorative intrusion. the actual pyramid-shaped playing volume is wholly contained by that protected box.

the two variants retain the current shared enclosure, all eight hoop sizes/heights, rebound geometry, floor, spectator stands, scoring actors, native game mode and sporting distances. the September 25 footprint amendment doubles floor area relative to September 16 and moves both goal assemblies outward; see `arena-footprint-20260925.md`. only environment actors use the `BB.Environment.v1` tag, and their primitive components use `nocollision` with overlap events disabled. scenery cannot change ball rebounds, catching, player bounds or referee marks. the stage verifies ordinary arena collision again after map saving/reloading.

the original surface inputs are `T_BB_RedSandstone_Albedo.png`, `T_BB_Adobe_Albedo.png` and `T_BB_RedwoodBark_Albedo.png` under `SourceArt/Environments/Textures`. these are generated base-color art, not calibrated photogrammetry or complete physically based texture sets. materials use world-space triplanar projection with restrained tints and roughness, preserving physical detail size on large surfaces and differently scaled instances. foliage is geometry rather than translucent cards, and the sea has low-amplitude real vertex movement.

## staging and verification

run the editor bridge with `stage_arena_environments.py` and `{"dry_run": true}`, then `{"dry_run": false}`. the helper only accepts the owned UE5.8 developmentharness project and a clean, stopped editor. the source map is `/Basketbroom/Maps/BB_Regulation`; it is never overwritten. new variants are made with `NewLevelFromTemplate`.

before mutation, the helper checks all source hashes, exact destination ownership and current enclosure dimensions. existing destination packages are backed up to an immutable `.local/environment-stage/<attempt>/backups` folder. it then imports only the original environment assets and replaces exactly nine old, verified background/light actors in the duplicated maps. an actor label alone never grants ownership. every other actor's identity, class, component settings, material references and transform must match the source map.

after authoring, the helper verifies no environment collision, runs actual enclosure/goal collision checks before save and after reload, confirms the native regulation game mode and restores the original map. a complete content hash comparison rejects saved changes outside the exact map/mesh/material/texture allowlist. re-running the stage replaces only the same owned environment actors and assets; unexpected sporting differences cause a failure rather than an overwrite. receipts never claim gameplay tests that were not run.

seventeen offline tests currently pass: source hashes/current dimensions, rotated and scaled placement, outward surface winding, triangle crossing with all vertices outside the box, valid overhang clearance, rejection of intruding scenery, exact package allowlist, false backdrop ownership, rejection of changed or missing sporting actors/materials/transforms, exact triple-size giants, paired trunk/crown transforms, varied size/depth distribution and whole-tree clearance.

saved ue5 map and editor visual acceptance are recorded in the september 25 checkpoint below. packaged acceptance for the newest giant-tree build remains separate. the native creator kit must import these original sources separately through its supported engine. ue5 `.uasset` files are never a native port mechanism, and no native map registration, entrance, dungeon return or full match integration is claimed by this environment source stage.

## september 25 giant-tree source amendment

the grove keeps all 49 original tree positions and yaw angles. each tree's trunk and crown receive the same uniform scale, preserving their fit and the original three mesh variants. the manifest records the prior instance scale, multiplier, size class and depth band for review; its additive forest metadata uses revision `varied-grove-eight-triple-size-giants-v1`.

source generation checked all 2,772,322 transformed redwood triangles against the enlarged arena's protected envelope and found zero intrusions. a separate test confirms even the full transformed bounding boxes of every trunk and crown remain outside that envelope. the existing 438.637 × 136.608 m enclosure, hoop geometry, red-rock venue, coastal features and all mesh source bytes remain unchanged. the tree increase adds no mesh instances or triangles. native creator kit maps are outside this amendment.

## september 25 giant-tree saved and visual checkpoint

stage `.local/environment-stage/20260925-102023-131022-71635645/result.json` completed with both ue5 environment maps saved/reloaded, the source map preserved and content changes confined to the allowlist. its manifest sha-256 is `283b6fec84a34ba7d9e5510400be317c93c210a04ea0b8bcd5c2a549a5b9b080`, matching the archived source recipe. the seventeen portable environment checks passed in the root development session. the stage itself explicitly reports that it did not test gameplay.

the root assistant directly inspected the actual hero preview `.local/environment-renders/20260925-062135-redwoods.png` and accepted the giant-tree composition for the prototype. this is editor visual acceptance, not packaged gameplay or frame-rate certification. the asynchronous preview request retains its original `requested` status; the captured image and separately recorded review provide the visual evidence.

`Docs/validation-environments-20260925.json` records the source/stage/preview hashes, grove counts, clearance results, seventeen test names, direct visual review and limitations. exact copies of the stage receipt, manifest, preview and capture-request provenance are retained read-only under `.local/validation-archive/20260925-102420-172-redwoods-dce6342150034adbaacf1ef0c28ceb31/`.

the final candidate `.local/PackageWork/Development-20260925-062224-613/package-result.json` built successfully and was promoted to the desktop launcher. its own review confirmed all three maps rendered; redrock regulation and redwoods bloodbroom entered live play with running clocks and observed scoring. the giant, medium and smaller redwoods and coastal opening were visible. classic was checked through rendering and its lobby only; live play there was not verified. both loopback connection/join/map-travel checks passed, without certifying gameplay replication or remote multiplayer.

`Docs/validation-package-20260925.json` preserves the candidate-specific acceptance and promotion evidence. promotion receipt: `.local/package-promotions/20260925-102909-772-e28cca76c916408493343653ebb20e8d/promotion.json`. the previous desktop pointer and package were retained. these are prototype environment and mannequin visuals; realistic adult hogwarts-style characters are a newly requested, unfinished addition.


## september 15 staging checkpoint

the first ue5 stage saved all 54 allowed packages and preserved source content. Receipt: `.local/environment-stage/20260915-131953-509706-d0c0c143/result.json`; sha-256 `2ab5c68fd57b1be1408a5b2688f6b42126e75b5a599d963457e34fa46bc8927e`. root reported a visual defect: front-facing cameras see the cliff rear, indicating possible obj y-axis reflection. this is unresolved at checkpoint and the venue art is not visually accepted.

`Tools/repair_arena_environment_axes.py` defaults to a read-only imported-bounds/topology audit. it compares all 30 actual static-mesh signed bounds and triangle counts against exact source manifests, requires one consistent handedness across asymmetric meshes, and rejects unexplained transforms. if y reflection is proved, execution compensates only each owned environment mesh actor's y scale, preserving positions, rotations, all sporting actors and every mesh/material asset. it backs up, saves/reloads and checks both maps. it does not rotate cameras to conceal incorrect geometry. the diagnostic/repair has compiled but has not been run at this checkpoint. its report explicitly distinguishes signed-bound proof from a full vertex-by-vertex export comparison.

the native broom helper `Tools/test_hlck_native_broom.py` also exists: read-only preflight by default; explicit execution activates only the witnessed house-broom inventory record, confirms the real native returned tool and local controller possession of a flyingbroom, observes flight, and normally dismounts/restores initial tools. ascent and end-pie are separate explicit options. only captured native apis are used; no native flight result is claimed yet. `{"operation":"inspect"}` reports an existing observer; `{"operation":"cancel"}` cancels pre-activation observation or requests normal cleanup for an activated test.
