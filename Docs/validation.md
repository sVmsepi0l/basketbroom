# Basketbroom alpha validation

Validated locally with Unreal Engine 5.8.1 and Windows 11; native gameplay, practice transitions/rematch, local networking, and packaged connection were checked on 2026-09-12, with the recorded audio evidence below from 2026-09-10. The active project uses the compiled native runtime and `/Basketbroom/Maps/BB_Regulation`. The earlier Blueprint training mode remains available as `/Basketbroom/Maps/BB_Arena`.

## Native alpha milestone

- Native Editor and Win64 Development game compilation succeeded using Visual Studio 2026, MSVC **14.51.36257**, Windows SDK **26100**, and the .NET Framework **4.8 SDK**.
- The regulation map was staged, saved, and enabled with `BBGameMode`.
- **35 native PIE integration checks passed**, with 0 failed and 0 not run. The latest run took 27.328 seconds and exercised the compiled native GameMode, GameState, rider, and ball classes. The harness waits for observable state and separates queued requests to respect the server's input throttle.
- The checks cover the sixteen-slot roster and seven balls; lobby/live/stoppage clocks; host team and position selection; live position locks; flight through the open crown and envelope limits; floor/net rebounds; free/carried No Crown; wrong/reverse/rim goal rejection; actual 13/37-point goals; role eligibility; and continuous Snipe progress, reset, 69-point award, and timeout.
- Native Win64 Development cooking, staging, packaging, and archiving succeeded. `.local/latest-package.json` records a completed native package. Both regulation and training maps are included.

Packaged native headless startup loaded the regulation map without errors. All **17 same-process network checks passed** in 20.468 seconds, including client RPCs, host-only control, score replication, client flight reaching the server, and pickup/throw possession replication. The pickup fixture now lets native ball Tick expire the 0.25-second kickoff grace period; freezing that tick had prevented pickup and was a fixture error, not a demonstrated replication failure. Two independent packaged processes also completed a loopback connection, join, and map load in 20.464 seconds on 2026-09-12. These results do not establish remote transport, replication under latency, or interactive gameplay between separate processes. Native packaged visual/input verification remains separate work. See `native-validation.md` for fixture boundaries and `networking.md` for network scope.

All **11 native audio integration checks passed** in 4.781 seconds. They loaded the original SoundWave assets and observed native pickup, throw, whole-ball goal, and Snipe-catch events starting the expected audio components. Unchanged possession/score and the Snipe timeout did not repeat cues, and finished cues released their components. `.local/native-audio-test-results.json` records these observations. Speaker output, listening/mix quality, packaged audio cooking, remote-client timing, and bounce feedback were outside this suite.

`Play.ps1` defaults to `-Mode Auto`, which uses the latest native package. `-Practice` selects accelerated native clocks; `-Mode Training` selects the earlier training map. Native position keys **1–6** and team key **T** change the roster in the lobby or at a stoppage. The host uses **Enter** to start/resume or begin a rematch after certified `FINAL`, and **P** to stop. Regulation retains four 44-minute quarters and a Snitch release at 22 live minutes; practice uses three-minute quarters and a Snitch release at one live minute.

The practice Snitch/rematch suite passed **19/19 checks in 28.125 seconds**. It observed the Snitch inactive at 59.667 live seconds and active at 60.001, partial capture progress, reset on release, a continuous hold awarding exactly 150 points, and the correct final winner after a two-game-second review. The host's normal ready action then started a live rematch with practice configuration, quarter one, reset scores/clocks, identical actors/roles, clear held/stun/capture state, and a newly scheduled Snitch. It restored the editor URL/play settings and the disposable world's time dilation, then ended PIE. Time dilation was 8x approaching release, 1x across the release boundary, 0.1x while following the moving Snitch for capture, and 1x for certification/rematch. The largest capture step was 0.0333 game seconds. Human piloting, normal-speed chase difficulty, 22-minute regulation release, and the 300-point overtime catch remain outside this fixture.

The opening suite passed **11/11 checks in 58.937 seconds**. Two actual Quark goals established a 37–37 tie; actual practice clocks carried that score through four quarters, 120-second overtime, and Donnybrook. The suite used 20x dilation only in its disposable PIE world. It checked whole-rider placement behind the required lines, neutral equipment marks, preserved positions at ordinary stoppages, and Donnybrook's goal-line opening with only Quarks and Snipe active. It did not inject scores or phases. False-start adjudication, CPU tactics, remote replication, and full-length regulation timing remain outside this suite.

The Bludger suite passed **9/9 checks in 171.671 seconds** using 0.15x PIE dilation and physical fixtures. It checked short self-toss control retention, resets after cumulative ten-foot travel and short floor contact, hits during pickup lockout, initial thrower clearance and later self-hit, nearest eligible opposing-Hurleyback restart, distance tie-breaking, and exclusion of a stunned receiver. These are native ball/rules observations, not Hurley striking or human contestability validation. Details are in `.local/native-opening-test-results.json` and `.local/native-bludger-test-results.json`.

In the Sep12 packaged native practice build preceding these opening changes, physical key **6** selected Scout, **T** switched to Copper, and **Enter** started the match, with `LIVE` and a 2:59 clock observed in the UI. Physical **P** and **Tab** verification remains pending. The automated stoppage/rematch results above exercise the native action path; they do not establish physical P delivery or Enter at the final-result screen.

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

The arena and HUD have received visual review, but riders remain procedural placeholders and no AAA-quality or sustained-performance milestone is claimed. The new Hurley prop compiled successfully and awaits rendering inspection; its provisional 103 cm length and shallow 36 cm-wide head do not fit the current oversized Bludger. It adds no striking mechanics, and no equipment-dimension certification is claimed. Four original training sounds and their Blueprint event wiring were built. Native audio event integration passed its focused suite; a listening pass remains pending.

Reports in `.local/` describe individual runs and are regenerated. Re-run `Tools/test_native_playable.py`, `test_native_snitch.py`, `test_native_openings.py`, `test_native_bludgers.py`, `test_native_network.py`, and `test_native_audio.py` after relevant native changes; use `test_playable.py`, `test_bots.py`, and `test_flight.py` for the retained training mode. Rebuilding or launching a package does not automatically repeat these checks. Read the README for play commands and the implemented scope.
