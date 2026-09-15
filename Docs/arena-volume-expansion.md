# Arena volume expansion

**Requested September 15, 2026. Status: implementation, saved-map staging, targeted runtime checks and Windows packaging complete.** The user requested a **40–50% increase in enclosed arena volume**. This applies to Basketbroom and Bloodbroom in the standalone UE 5.8 game and the native Creator Kit port.

Use **45% more volume** as the initial target. Uniform scaling of the enclosure is the implementation default: `scale = (1.45)^(1/3) = 1.13185119596`, or approximately **13.19% more length, width and height**. The source, C++ targets and both standalone/native saved arenas now use these dimensions. The prior package and earlier Play receipts describe the pre-expansion arena; fresh expansion results are recorded below.

## Measurement

Measure the actual enclosed space from the trampoline floor through the hollow pyramidion roof. The pre-expansion shared geometry in [BBArenaGeometry.h](../DevelopmentHarness/Source/BasketbroomRuntime/BBArenaGeometry.h) has half-length 6850.8 cm, half-width 3200.4 cm, eaves at 4206.24 cm and an apex at 6309.36 cm. Its enclosed volume is:

`V = (2 * HalfLength) * (2 * HalfWidth) * (EaveHeight + (ApexHeight - EaveHeight) / 3)`

The finished volume must be between `1.40 * V` and `1.50 * V`, targeting `1.45 * V`. Use the enclosing net's footprint for this measurement; the historical 420-foot goal-to-goal distance omits the space behind the goal planes. Preserve the upward-pointing, hollow four-face cap and the rebound behavior established by the [pyramid-net amendment](pyramid-net.md).

## Source audit before implementation

The September 15 source audit resolved an important naming difference: `BBArenaGeometry.h::HalfLength` is the **end-net plane**, while `build_arena.py::HALF_LENGTH` is the **goal plane**. The existing 450 cm behind-goal bay belongs to the enclosed footprint. Scale the goal-plane placement and bay depth together; adding an unchanged 450 cm after scaling the pitch would miss the uniform-volume target.

At the 45% target, enclosure half-length is 7754.086173 cm, half-width 3622.376568 cm, eaves 4760.837775 cm and apex 7141.256662 cm. The goal planes move to ±7244.753135 cm and bay depth becomes 509.333038 cm. The enclosed volume is approximately 430374.351 m³ before and 624042.809 m³ after. These dimensions now drive the shared source contract; saved-map acceptance is recorded separately.

Use explicit goal-plane and end-net constants across the C++ runtime and source generator. Preserve current hoop apertures, 35-foot hoop spacing and 69/100-foot hoop-center heights, along with the fixed 44-foot free-shot minimum, 22-foot restart offset and 13-foot exclusion distance. Reposition arena-dependent scenery and marks selectively; do not scale the whole world or the riders and equipment.

The implementation must replace duplicated geometry in ball scoring, match admissions/openings, bot approaches, penalty-shot targets and conduct-mark bounds. Training has separate Blueprint generators: its current 3140 cm side-ball limit should become half-width minus the actual ball radius. Active collision and network tests also contain fixed dimensions and goal-adjacent fixtures that must move with the venue. Retired Crown-rule tests are historical evidence, not active geometry specifications.

Native expansion needs its own bounded staging receipt. The existing roof stage covers only four roof meshes, one material and two maps; it cannot claim preservation for changed floors, walls or goal placements. Extend the verified map-amendment chain used by the arena, dungeon and anchor inspectors. Keep the native PlayerStart and exit where they are if their clearance checks remain valid, preserve existing material edits, and retain all pre-expansion receipts.

## Implementation and acceptance

- Update the shared dimensions, generated floor/wall/roof geometry, collision, authoritative ball and rider bounds, owner prediction, held balls and Snipe/Snitch paths together. The visual enclosure and playable bounds must agree.
- Reposition arena-dependent goals, spawn locations, restart markers and gameplay zones coherently. Player/ball/broom size, hoop aperture sizes and sporting distances are separate parameters; the arena scale factor must not automatically multiply them. The confirmed Moderate free-shot minimum remains 44 feet from the attacking goal plane, with sideways position and altitude retained.
- Apply the same enclosure to Basketbroom and Bloodbroom and update the affected training geometry. Check flight room, goal visibility, chase capture, shot/restart placement and rebound behavior in both modes.
- Reimport original sources into the native Creator Kit, update only the owned arena geometry and required placements, then recheck roof faces/seams/apex, native player spawn and exit setup. Preserve unrelated scene content and registration data. UE 5 packages are not a port mechanism.
- Verify the measured volume ratio, real collision and gameplay bounds before creating a new Windows package. Keep the current native Play and roof receipts as evidence of the earlier dimensions; the enlarged arena needs fresh results.

## Source implementation

`Tools/arena_dimensions.py` is the dimension source for geometry generation, training graphs, fixtures and the generated C++ header. The rule configuration records both goal-plane length and enclosed length, including the behind-goal bays. Runtime scoring, restart placement, bot approaches and chase routes use the shared dimensions. Chase route timing compensates for the expanded route amplitudes so the size change does not accelerate the balls.

The bounded saved-map plan contains 905 original arena actors and ten changed mesh sources. It moves or stretches the relevant placements while preserving hoop geometry and the remaining original mesh bytes. Native and UE5 staging preserve actor identities, components and material references, with byte backups before authoring and collision checks after saving/reloading.

The UE5.8 editor and Windows Development game targets compiled successfully on September 15. No C++ source changed after those builds. The final portable rule/arena/expansion runs passed **133 unique tests**: 55 rules, 22 arena/training contracts and 71 expansion checks, with 15 overlapping contracts counted only once. The separate displayed-hit fixture suite passed five checks, and `git diff --check` passed. Saved-map, runtime and completed package evidence follows.

Exact source/import provenance bytes are pinned in `.gitattributes`. The eight unchanged OBJ meshes retain their existing CRLF bytes in Git; their staged differences are line-ending storage only. The ten expanded OBJ meshes, source manifests, rules and builder retain the bytes used for staging. All 25 relevant index blobs were checked against the working files before committing; no imported source or saved package was regenerated for this fix.

## Standalone saved-map acceptance

On September 15, UE **5.8.1** selectively amended and saved/reloaded `/Basketbroom/Maps/BB_Regulation` and `/Basketbroom/Maps/BB_Arena` at **1.45 times the original enclosed volume**. The stage changed exactly ten original-source mesh packages and two maps. It moved existing owned geometry in place and updated the explicit training starts/homes without rebuilding either scene or its materials.

The successful receipt is `.local/arena-expansion-stage/20260915-114541-416254-21b6ab9a/results.json` (SHA-256 `42c4d0014e3ac6df17b2e20bdf846ce973349d4eecd0b06cb1f3d4d8416ba258`), referenced by `.local/arena-expansion-success.json`. Its immutable attempt directory contains the 12 original package backups and actor snapshots. Both maps passed actor/component/material preservation and retained their game modes; mesh material interfaces and slot names were verified across reimport and reload. All material-file bytes were preserved, and the original `BB_Regulation` map was restored cleanly.

**324 actual collision queries passed**: 54 per map at the original baseline, 54 after expansion before saving, and 54 after saved reload. They bracket the floor and all four walls, the roof faces/hips/apex and hollow eaves, and the centers and aperture edges of all eight hoops. Hoop radii, heights and spacing stayed fixed. These are editor-world geometry checks; the stage receipt's original `runtime_validation_pending` flag describes that checkpoint, while the subsequent runtime receipts below provide separate acceptance.

## Standalone runtime acceptance

The following September 15 runs passed **142 case executions across 11 disposable PIE sessions**, including the separate regulation/Bloodbroom cases. Each receipt folder is under `.local/`; failed and not-run attempts remain archived and are excluded from these totals.

- **Training, 10/10:** `arena-expansion-validation-training-20260915-074700`. The actual Blueprint graphs rebound balls from all four roof faces, confine the pawn and large endpoint overshoots, preserve the hollow old ceiling plane and live clock, then restore the original map.
- **Regulation and Bloodbroom roof gameplay, 23/23 each:** the first two reports in `arena-expansion-validation-core-20260915-075439`. They cover faces, hips, apex, high-speed containment, 0.75 restitution with tangential velocity preserved, native pickup/carry, rider movement, Snipe/Snitch route containment and actual 13/37-point goals. That folder's later openings attempt was not run and is not counted.
- **Regulation and Bloodbroom admission, 9/9 each:** `arena-expansion-validation-admission-20260915-080002`. The enlarged side strip supports actual Quark pickup and a continuous Snipe catch worth 69; protruding ball spheres or rider capsules cannot initiate interaction below the apex.
- **Regulation near Quaffle free shot, 15/15:** the first report in `arena-expansion-validation-free-20260915-075826`. A real illegal hit creates review, the host stages and completes the free shot, the near mark moves to 44 feet from goal while retaining sideways position/altitude, defenders remain 22 feet away, and the keeper receives the protected restart. The later failed Bloodbroom attempt in this folder is excluded.
- **Openings and period transitions, 11/11:** `arena-expansion-validation-openings-20260915-080932`. Actual goals establish a tie, then native practice clocks advance through four quarters, overtime and Donnybrook with the required rider/ball layouts and preserved neutral sporting marks.
- **Bloodbroom far Quark free shot, 15/15:** `arena-expansion-validation-free_blood-20260915-081047`. A genuine displayed Arresto confirmation followed by Stupefy applies the stun before double-tap review, followed by the real free-shot, score and restart flow.
- **Two-world roof replication, 6/6 per variant:** `arena-expansion-validation-network-20260915-081132`. Distinct authority/client worlds observe the actual rebound, converge while contained, and preserve score, custody and live clock state.
- **Regulation high-altitude far Quark free shot, 15/15:** `arena-expansion-validation-free_high-20260915-081517`. The original and resulting shot marks retain `y = -650 cm` and `z = 4400 cm`, at approximately `x = -4243.953 cm`, 3000.8 cm from goal. The shot scores through the normal release and protected-restart flow.

Training, the two roof runs, the two admission runs and the near Quaffle shot used **NullRHI**. Openings, the successful Bloodbroom shot, both network runs and the high-altitude shot used **rendered PIE**. The network/openings setup records `settings_source = editor_config`: Listen Server was configured with the editor closed, then checked through actual authority and owning-client behavior. It does not claim the missing Python enum was read back or that the mode was set through the UI.

Fixture sequencing was corrected without relaxing gameplay rules. Drivers now avoid redundant queued role changes, wait 90 ms after an observed variant/role change before kickoff to respect the native 60 ms action limit, and allow ordinary pickup/casting cooldowns to expire before testing admission or eligibility. No effect, cooldown, score, custody, referee decision or acknowledgment is injected to make these cases pass.

The shared double-tap fixture now waits for the real owner's critical-notice countdown to fall from its undrawn 2.25 seconds to at most 1.90 seconds, while the target is still impeded and the caster is ready. This observes actual HUD display time before the native receipt; queued text alone is insufficient. The earlier NullRHI Bloodbroom attempt landed both effects but produced no confirmed double-tap review and remains a failed receipt. The rendered retry recorded **0.748 seconds of notice time remaining and 1.498 seconds of impediment remaining before Stupefy**, then passed the unchanged hit/foul assertions. No C++ policy change was required.

Fresh unedited engine captures were reviewed: [expanded flight view](Screenshots/arena-expanded-flight.png) and [expanded roof view](Screenshots/arena-expanded-roof.png). The roof capture was taken at match end. These captures document the current arena appearance; the automated results establish the targeted mechanics and local replication, not sustained frame rate, internet multiplayer or full Hogwarts gameplay parity.

## Expanded Windows package

The UE5.8.1 Development build/cook/package completed successfully on September 15 with both saved maps. The new archive is `.local/Build/Development-20260915-081623-488/Windows`; `.local/latest-package.json` and the existing desktop shortcut now select its `BasketbroomDev.exe`. The build log is `.local/PackageWork/Development-20260915-081623-488/BuildCookRun.log`. Older packages remain intact.

The main runtime executable SHA-256 is `BD1DEF8DCFA5E7E05D4CCE913EEAFB157779F107A5EEBF4067750BBD0C468B0B`. Its expanded map/content payload was cooked into the new archive. Two-process loopback connection checks passed for the standard and Bloodbroom launch URLs: `.local/packaged-network/20260915-081752-416-1bfdb82c/result.json` and `20260915-081814-429-4adc8a47/result.json`. They verify the actual loopback bind, tagged client handshake and regulation-map load; they do not establish packaged gameplay replication or internet connectivity.

Fresh **1600×900 D3D12 startup captures** from the packaged executable were visually reviewed in both modes. Their receipts are `.local/packaged-render/20260915-081918-022-regulation/result.json` and `20260915-082016-903-bloodbroom/result.json`. Both show the expanded enclosure and lobby/HUD, with the expected Basketbroom or Bloodbroom label and no engine errors. These were lobby rendering checks with sound disabled; gameplay evidence is from the separate PIE suites above. Each helper stopped only its own retained process handle.

The temporary editor Listen Server setting was restored to its original Standalone value after the rendered tests and before packaging (`.local/arena-expansion-network-config.json`). All 28 pre-existing native material edits remain byte-identical to their preservation backup. The Creator Kit was left open in the clean, saved enlarged dungeon.


## Native saved-map acceptance

On September 15, both `/Basketbroom/Maps/BB_Arena_Port` and `/Basketbroom/Maps/Basketbroom_DungeonMap` were saved and reloaded at **1.45 times the original enclosed volume**. The amendment changed ten original-source mesh packages and two maps, moving or resizing 883 existing actors in each map. It preserved hoop apertures, spacing and heights, the fixed 44-foot shot and 22-foot restart distances, and the native PlayerStart and exit locations.

The successful receipt is `.local/hlck/arena-expansion-stage/20260915-113602-895613-1a969573/result.json` (SHA-256 `616c932f88003be1cde5735cbec12b8dcf8943853c1b0f37e8469874190c725e`). Its two map chains reach the original arena/anchor receipts through the earlier roof amendment, with verified original byte backups and final hashes for all 12 changed packages. The prior failed import attempt and its backups remain intact.

**356 real collision queries passed**: 89 before saving and 89 after reloading each enlarged map. They cover roof faces, hips, apex and open eaves; floor and wall boundaries; hoop-center clearance; and native entry/exit headroom. The subsequent dungeon/registration/anchor inspection passed **27/27 checks**. These are editor-world geometry and setup results; the separate observation of expanded native Play is recorded below.

All existing material-file bytes, including the 28 pre-existing material edits, were preserved. Actor identities, component assignments, native game modes and registration were checked across reload. The comparison explicitly accounts for native reload resetting the existing fog actor from -800 cm to the origin and creating an empty, untagged SceneRig camera manager; the stage does not reposition the fog or delete that manager. Text colors are compared as RGBA values rather than temporary wrapper addresses. Original scalar mesh-slot names were not recorded before the interrupted import, so the receipt claims only their verified preservation during the subsequent resume; existing scene material assignments stayed unchanged.

## Native Play observation after expansion

The enlarged dungeon passed **17/17 checks** in the existing user-started Play session on September 15, observed from **12:07:40.332610 to 12:07:47.931909 UTC** in native process 20652. The 16 native player/runtime-integration checks passed alongside the advancing-world-clock check: game time advanced 7.698 seconds during 7.593 seconds of observation, with all checks satisfied for two seconds. The observer was read-only; it did not start or stop Play, inject input, save assets or register the dungeon.

A subsequent, separate owned-session Stop ended Play normally. Cleanup passed at **12:09:05 UTC**, the saved dungeon/anchor inspection passed **27/27** again at **12:09:06 UTC**, and the following checkpoint confirmed Basketbroom active, the original dungeon open, no PIE worlds, no dirty packages and no remaining observer.

The six archived receipts and their hashes are in `.local/hlck/expanded-live-pie-success/413b9c661df6493bbb98da19a246848d/manifest.json` (SHA-256 `794c47e5da55f7c06366330cd6fb1a6453460ed35f5526722021612ec0d96e48`), referenced by `.local/hlck/native-expanded-live-pie-success.json`. Earlier roof, startup and pre-expansion Play archives remain unchanged.

This proves current native readiness in the enlarged arena and clean shutdown. It does not measure startup, verify pre-Play file preservation, establish sustained frame rate, or prove entry/return travel, scoring, catching, a full regulation match or Hogwarts multiplayer.
