# Pyramid-net validation �2026/09/-14

This record covers the closed roof revision in the standalone Unreal Engine 5.8.1 prototype. It does not certify full regulation, a completed Hogwarts Legacy mod, final art, remote multiplayer, or physical controller transport testing.

## Source and assets

- Native editor compilation passed using the installed UE 5.8.1 engine.
- 55 Python rules tests passed, including default rejection of obsolete Crown exits without state changes. Historical Crown behavior is tested only with an explicit legacy configuration.
- Portable C++ suites passed: 69 regulation cases, 24 conduct-award cases, 35 Serious-shot cases, and 10 admission cases.
- Four sloped collision triangles meet at one apex; the underside has no horizontal face. Source checks covered 289 surface samples and shared seams.
- Both saved maps passed 38 collision queries combined, from inside and outside the faces, hips and apex, including clear passage through the former horizontal roofline. The staging audit preserved unrelated actors and each map's game mode.
- BP_BBMatch and BP_BBBall were rebuilt for training; a later HUD-only pass changed the obsolete roof label to "PYRAMID NET". Each targeted stage verified every other saved asset and map remained unchanged.

Receipts: `.local/pyramid-editor-build.log`, `.local/pyramid-net-stage/20260914-155911-755622/results.json`, and `.local/training-pyramid-stage/20260914-160016-650758/results.json`.

## Native gameplay

The new roof suite passed all 23 checks in each of Basketbroom and Bloodbroom. It exercised all seven balls, four faces, four sphere-inset hip seams, apex contact, a measured low-frame-rate high-speed shot, 0.75 normal restitution, ordinary pickup/carry, rider capsule containment, real scheduled Snitch release, and ordinary 13/37-point goals. No score, custody, clock, activation or outcome was injected; physical fixtures arranged starting transforms/velocities and isolated CPU ticks. Temporary frame cap, time dilation and Practice URL were restored.

Actual roof-contact Serious-shot scenarios passed 13 checks per mode: a net miss awards zero points and follows the existing protected defending restart. Merely crossing the former roofline does not end the attempt.

Receipts: `.local/pyramid-validation-roof-20260914-155800/summary.json` and `.local/pyramid-validation-roof_shots-20260914-160103/summary.json`.

## Visual inspection

Real editor and native PIE renders were inspected from outside and beneath the roof. The net forms a broad pyramid with iron hips, copper sleeves and open sightlines through its four faces. No opaque ceiling or horizontal cap is present. This is prototype art.

Review image: `.local/pyramid-net-ui/pyramidion-arena.png`.

## Regression and training results

- Serious-shot matrix: 104/104 checks passed across both modes, covering Quaffle/Quark makes, misses and timeouts.
- Penalty timing/admission/replacement edges: 60/60 passed.
- Native playable/controller/spell regressions: 73/73 passed (35 playable, 18 controller bridge, 17 regulation spell, 3 Bloodbroom spell checks). These are automated game input checks, not fresh physical USB/Bluetooth testing.
- Training: 10/10 passed, executing the actual generated graphs for four-face rebounds, old-plane passage, extreme overshoot, DefaultPawn containment, state preservation and owned PIE/map cleanup. Actual training E-key pickup/held execution is not covered because that older graph has no reflected input bridge; native real pickup/carry passed separately.
- Two-world roof replication: 6/6 checks per mode passed. The server's actual bounce reached the client above the former eave plane, both trajectories stayed enclosed, and scores/custody/live clocks remained correct. This was local PIE with two distinct connected worlds, not a remote latency test.

Receipts: `.local/pyramid-validation-matrix-20260914-160205/summary.json`, `.local/pyramid-validation-edges-20260914-160453/summary.json`, `.local/pyramid-validation-solo-20260914-160609/summary.json`, `.local/pyramid-validation-training-20260914-160856/summary.json`, and `.local/pyramid-validation-roof_network-20260914-161016/summary.json`.

## Additional network checks

The existing two-world multiplayer suites passed 27/27 general/spell checks and 20/20 Serious-shot checks across both modes. The spell-foul fallback fixture now uses actual scored-ball restart reservations in place of the retired Crown reservation; this preserves the original scarce-ball award behavior under current rules.

Receipts: `.local/pyramid-validation-network_regressions-20260914-161023/summary.json` and `.local/pyramid-validation-network-20260914-161131/summary.json`.

The owned editor was closed after a clean-package checkpoint. Its original Standalone play mode, one client and single-process setting were restored; unrelated current preferences were preserved. Receipt: `.local/pyramid-network-settings-restored.json`.

## Packaged game

The first package built successfully at `.local/Build/Development-20260914-161309-327`; all three modes rendered and exited with code 0, and both two-process loopback checks passed. Visual inspection caught a stale "OPEN CROWN" subtitle in the training HUD, so the package was refreshed after a HUD-only correction. The gameplay binaries and maps were not changed by that correction.

The isolated HUD-stage receipt is `.local/training-pyramid-stage/20260914-161806-021428/results.json`. The final package is `.local/Build/Development-20260914-161847-377`. Basketbroom, Bloodbroom and training each rendered at 1600�900, showed the closed roof, and exited normally with code 0 and no logged runtime errors. Visual review confirmed the corrected training subtitle. The native executable hash matches the prior tested roof package; only the training HUD asset changed in the final refresh.

Final render/exit receipt: `.local/pyramid-packaged-visual-20260914-162042/results.json`.

Both final packaged two-process loopback connection checks passed, using ports bound only to 127.0.0.1. Receipts: `.local/packaged-network/20260914-162044-295-17be59de/result.json` and `.local/packaged-network/20260914-162105-045-7d4841cd/result.json`. These packaged checks establish connection/join and map travel; the separate two-world suites above establish gameplay replication.

The desktop launcher follows `.local/latest-package.json`, which points at the final package. Prior builds and the completed promotional video were preserved.

## Result and remaining development

The revision passed 378 focused Unreal gameplay/training/replication assertions, 193 portable C++/Python cases, saved-map collision checks, and final packaged startup/connection checks. Counts are assertions across scenario runs, not 378 distinct complete matches. Original editor play preferences were restored and test-owned game processes were closed.

Full regulation completion, remaining spell adapters and role abilities, longer/remote multiplayer playtests, playable Hogwarts Legacy integration, and final venue/character art remain ongoing. The source port now knows the pyramid assets and triangle collision, but its saved Creator Kit map was not rebuilt in this revision. The historical Crown entry points and tests do not establish current roof behavior.

The older broad `Tools/test_playable.py` fixtures were migrated to closed-roof expectations and syntax-checked, but were not rerun as part of this revision; the physical-only training suite above supplies the current runtime proof.
