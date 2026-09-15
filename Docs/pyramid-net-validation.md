# pyramid-net validation �2026/09/-14

this record covers the closed roof revision in the standalone unreal engine 5.8.1 prototype. it does not certify full regulation, a completed hogwarts legacy mod, final art, remote multiplayer, or physical controller transport testing.

## source and assets

- native editor compilation passed using the installed ue 5.8.1 engine.
- 55 python rules tests passed, including default rejection of obsolete crown exits without state changes. historical crown behavior is tested only with an explicit legacy configuration.
- portable c++ suites passed: 69 regulation cases, 24 conduct-award cases, 35 serious-shot cases, and 10 admission cases.
- four sloped collision triangles meet at one apex; the underside has no horizontal face. source checks covered 289 surface samples and shared seams.
- both saved maps passed 38 collision queries combined, from inside and outside the faces, hips and apex, including clear passage through the former horizontal roofline. the staging audit preserved unrelated actors and each map's game mode.
- bp_bbmatch and bp_bbball were rebuilt for training; a later hud-only pass changed the obsolete roof label to "pyramid NET". each targeted stage verified every other saved asset and map remained unchanged.

Receipts: `.local/pyramid-editor-build.log`, `.local/pyramid-net-stage/20260914-155911-755622/results.json`, and `.local/training-pyramid-stage/20260914-160016-650758/results.json`.

## native gameplay

the new roof suite passed all 23 checks in each of basketbroom and Bloodbroom. it exercised all seven balls, four faces, four sphere-inset hip seams, apex contact, a measured low-frame-rate high-speed shot, 0.75 normal restitution, ordinary pickup/carry, rider capsule containment, real scheduled snitch release, and ordinary 13/37-point goals. no score, custody, clock, activation or outcome was injected; physical fixtures arranged starting transforms/velocities and isolated cpu ticks. temporary frame cap, time dilation and practice url were restored.

actual roof-contact serious-shot scenarios passed 13 checks per mode: a net miss awards zero points and follows the existing protected defending restart. merely crossing the former roofline does not end the attempt.

Receipts: `.local/pyramid-validation-roof-20260914-155800/summary.json` and `.local/pyramid-validation-roof_shots-20260914-160103/summary.json`.

## visual inspection

real editor and native pie renders were inspected from outside and beneath the roof. the net forms a broad pyramid with iron hips, copper sleeves and open sightlines through its four faces. no opaque ceiling or horizontal cap is present. this is prototype art.

review image: `.local/pyramid-net-ui/pyramidion-arena.png`.

## regression and training results

- serious-shot matrix: 104/104 checks passed across both modes, covering Quaffle/Quark makes, misses and timeouts.
- penalty timing/admission/replacement edges: 60/60 passed.
- native playable/controller/spell regressions: 73/73 passed (35 playable, 18 controller bridge, 17 regulation spell, 3 bloodbroom spell checks). these are automated game input checks, not fresh physical USB/Bluetooth testing.
- Training: 10/10 passed, executing the actual generated graphs for four-face rebounds, old-plane passage, extreme overshoot, defaultpawn containment, state preservation and owned PIE/map cleanup. actual training e-key pickup/held execution is not covered because that older graph has no reflected input bridge; native real pickup/carry passed separately.
- two-world roof replication: 6/6 checks per mode passed. the server's actual bounce reached the client above the former eave plane, both trajectories stayed enclosed, and scores/custody/live clocks remained correct. this was local pie with two distinct connected worlds, not a remote latency test.

Receipts: `.local/pyramid-validation-matrix-20260914-160205/summary.json`, `.local/pyramid-validation-edges-20260914-160453/summary.json`, `.local/pyramid-validation-solo-20260914-160609/summary.json`, `.local/pyramid-validation-training-20260914-160856/summary.json`, and `.local/pyramid-validation-roof_network-20260914-161016/summary.json`.

## additional network checks

the existing two-world multiplayer suites passed 27/27 general/spell checks and 20/20 serious-shot checks across both modes. the spell-foul fallback fixture now uses actual scored-ball restart reservations in place of the retired crown reservation; this preserves the original scarce-ball award behavior under current rules.

Receipts: `.local/pyramid-validation-network_regressions-20260914-161023/summary.json` and `.local/pyramid-validation-network-20260914-161131/summary.json`.

the owned editor was closed after a clean-package checkpoint. its original standalone play mode, one client and single-process setting were restored; unrelated current preferences were preserved. Receipt: `.local/pyramid-network-settings-restored.json`.

## packaged game

the first package built successfully at `.local/Build/Development-20260914-161309-327`; all three modes rendered and exited with code 0, and both two-process loopback checks passed. visual inspection caught a stale "open crown" subtitle in the training hud, so the package was refreshed after a hud-only correction. the gameplay binaries and maps were not changed by that correction.

the isolated hud-stage receipt is `.local/training-pyramid-stage/20260914-161806-021428/results.json`. the final package is `.local/Build/Development-20260914-161847-377`. basketbroom, bloodbroom and training each rendered at 1600�900, showed the closed roof, and exited normally with code 0 and no logged runtime errors. visual review confirmed the corrected training subtitle. the native executable hash matches the prior tested roof package; only the training hud asset changed in the final refresh.

final render/exit receipt: `.local/pyramid-packaged-visual-20260914-162042/results.json`.

both final packaged two-process loopback connection checks passed, using ports bound only to 127.0.0.1. Receipts: `.local/packaged-network/20260914-162044-295-17be59de/result.json` and `.local/packaged-network/20260914-162105-045-7d4841cd/result.json`. these packaged checks establish connection/join and map travel; the separate two-world suites above establish gameplay replication.

the desktop launcher follows `.local/latest-package.json`, which points at the final package. prior builds and the completed promotional video were preserved.

## result and remaining development

the revision passed 378 focused unreal gameplay/training/replication assertions, 193 portable C++/Python cases, saved-map collision checks, and final packaged startup/connection checks. counts are assertions across scenario runs, not 378 distinct complete matches. original editor play preferences were restored and test-owned game processes were closed.

full regulation completion, remaining spell adapters and role abilities, longer/remote multiplayer playtests, playable hogwarts legacy integration, and final venue/character art remain ongoing. the source port now knows the pyramid assets and triangle collision, but its saved creator kit map was not rebuilt in this revision. the historical crown entry points and tests do not establish current roof behavior.

the older broad `Tools/test_playable.py` fixtures were migrated to closed-roof expectations and syntax-checked, but were not rerun as part of this revision; the physical-only training suite above supplies the current runtime proof.
