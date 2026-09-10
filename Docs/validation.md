# Basketbroom alpha validation

Validated locally on 2026-09-10 with Unreal Engine 5.8.1 and Windows 11. The active project now uses the compiled native runtime and `/Basketbroom/Maps/BB_Regulation`. The earlier Blueprint training mode remains available as `/Basketbroom/Maps/BB_Arena`.

## Native alpha milestone

- Native Editor and Win64 Development game compilation succeeded using Visual Studio 2026, MSVC **14.51.36257**, Windows SDK **26100**, and the .NET Framework **4.8 SDK**.
- The regulation map was staged, saved, and enabled with `BBGameMode`.
- **35 native PIE integration checks passed**, with 0 failed and 0 not run. The queued-input run took 27.343 seconds and exercised the compiled native GameMode, GameState, rider, and ball classes.
- The checks cover the sixteen-slot roster and seven balls; lobby/live/stoppage clocks; host team and position selection; live position locks; flight through the open crown and envelope limits; floor/net rebounds; free/carried No Crown; wrong/reverse/rim goal rejection; actual 13/37-point goals; role eligibility; and continuous Snipe progress, reset, 69-point award, and timeout.
- Native Win64 Development cooking, staging, packaging, and archiving succeeded. `.local/latest-package.json` records a completed native package. Both regulation and training maps are included.

Packaged native headless startup loaded the regulation map without errors. All **14 same-process network checks passed**, including client RPCs, host-only control, and score replication. Two independent packaged processes also completed a loopback connection, join, and map load in 19.85 seconds. These results do not establish remote transport, replication under latency, or interactive gameplay between separate processes. Native packaged visual/input verification remains separate work. See `native-validation.md` for fixture boundaries and `networking.md` for network scope.

`Play.ps1` defaults to `-Mode Auto`, which uses the latest native package. `-Practice` selects accelerated native clocks; `-Mode Training` selects the earlier training map. Native position keys **1–6** and team key **T** work in the lobby or at a stoppage. The host uses **Enter** to start/resume and **P** to stop. Regulation retains four 44-minute quarters and a Snitch release at 22 live minutes; practice uses three-minute quarters and a Snitch release at one live minute. The short native suite observes the Snitch's scheduled state, not its timed release or capture.

## Independent rules checks

The **54 Python rule-reference tests** passed. They exercise the separate engine-independent model, including rules beyond the playable scene's current scope. The portable C++ engine passed **60 scenarios**, including those 54 reference cases. Its test executable was compiled independently of Unreal. Neither suite certifies Unreal collisions, presentation, or networking.

Full regulation still has penalty-shot execution, wand gameplay, and officiating/adjudication gaps. Native phase logic in source and portable rule coverage do not mean every phase has received end-to-end gameplay validation.

## Retained training evidence

The earlier Blueprint mode passed **34 Unreal checks** on its rebuilt visuals and initial Ranger HUD:

- 15 PIE gameplay checks: playable pawn, clock, scoring in both directions, ball/hoop matching, rim clearance, rebounds, No Crown, chase-ball movement and timeout, and match expiry.
- 15 PIE AI checks: roster and references, autonomous possession and scoring, isolated Quaffle and Quark shooting cycles, protection of human-held possession, and stopping at match end.
- 4 flight checks after saving, unloading, and reloading the arena: clear spawn/corridors, correct actual spawn, horizontal movement, and vertical movement with collision enabled.

The seven-stage training authoring pipeline completed. The final chase HUD fixes use consistent nearest-distance samples, a projected target label, screen-edge text clamping, and an off-screen turn hint. All 15 gameplay checks passed again after that rebuild; the final HUD compiled and was visually inspected in PIE. `Screenshots/training-flight.png` is an actual render from that training build, with an editor-only camera presentation fixture and scores from the running game. It is not a screenshot of the native regulation HUD.

Training Win64 Development packaging succeeded. An earlier visible packaged launch displayed a live scrimmage independently of the editor. The final training package also loaded `BB_Arena` with `BP_BBGameMode_C` in a separate headless process in 0.098 seconds without logged errors, then was stopped. Its final marker's visual check was in PIE. Training interactive input checks verified E pickup, mouse aiming/throwing, and a 13-point Quaffle goal. These observations remain training evidence, not native packaged validation.

## Limits and repeatability

PIE integration tests alter transient copies and stop or restore them. The native suite arranges physical fixtures, then observes actual gameplay requests and outcomes; it does not inject scores, ownership, capture progress, or clocks. Its isolated CPUs do not establish full-roster autonomous match quality. Flight checks inject movement input; physical key timing and flight feel need human playtesting. Continuous physical E-key chase capture, difficulty, match balance, and the audio mix also need further playtesting.

The arena and HUD have received visual review, but riders remain procedural placeholders and no AAA-quality or sustained-performance milestone is claimed. Four original training sounds and their Blueprint event wiring were built; native audio integration and a listening pass remain separate work.

Reports in `.local/` describe individual runs and are regenerated. Re-run `Tools/test_native_playable.py` after native changes; use `test_playable.py`, `test_bots.py`, and `test_flight.py` for the retained training mode. Rebuilding or launching a package does not automatically repeat these checks. Read the README for play commands and the implemented scope.
