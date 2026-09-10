# Native gameplay validation

`Tools/test_native_playable.py` is an asynchronous, single-world Unreal Engine 5.8 PIE integration suite for `BBGameMode`, `BBMatchState`, `BBRiderCharacter`, and `BBBall`. It is separate from the playable training Blueprint tests and the portable C++ rules tests.

**Current status, 2026-09-10: 35/35 PASSED.** The compiled native module loaded in Unreal Engine 5.8.1 and the complete single-world PIE suite passed in 27.343 seconds after the queued-input update: 35 passed, 0 failed, 0 not run. The report is `.local/native-playable-test-results.json`, with the observed native GameMode, GameState, and pawn classes and the `UEDPIE_0_BB_Regulation` world recorded. The regulation map is staged and enabled in the project.

Native Editor compilation and Win64 Development game compilation, cooking, staging, packaging, and archiving also succeeded. The local toolchain is Visual Studio 2026 with MSVC 14.51.36257, Windows SDK 26100, and the .NET Framework 4.8 SDK. `.local/latest-package.json` records a completed package with `NativeRuntime: true`. A headless native package loaded the regulation map with BBGameMode without errors. All fourteen same-process networking checks passed, and two packaged processes completed a loopback join and map load; see `networking.md` for the narrower scope of each result. Native packaged visual/input inspection remains separate work.

## Repeat the suite

1. Complete the supported MSVC/Windows SDK setup described in the repository README, then run `Build-Native.ps1 -Target Editor` successfully. Close and reopen the editor so it loads the resulting native DLL.
2. Run `Tools/stage_regulation.py` in the UE5.8 editor. It derives `/Basketbroom/Maps/BB_Regulation` from the existing arena and assigns the native GameMode. Select that map and stop any existing PIE session.
3. Run `py C:/Git/basketbroom/Tools/test_native_playable.py` in the Unreal console, or submit that script through the existing `Tools/editor_bridge.py` mailbox using a unique request ID. No other Basketbroom integration suite should be active. Avoid keyboard/mouse gameplay input until this runner finishes.
4. Read `.local/native-playable-test-results.json`. The console/mailbox result `started` only means the Slate callback was registered. The JSON report's final `status` is the result.

The suite starts its own fresh PIE session and always ends it. It changes only transient PIE copies and does not save a map. It declines an existing session, a missing native DLL/class/fixture bridge, or an unsuitable engine with `not_run`. A missing native world after 30 seconds is also `not_run`. Exceptions/timeouts are `error`, failed observations are `failed`, and `passed` requires all planned cases to have run and passed. Remaining cases retain `not_run` after an interrupted run. The default wall-time limit is 240 seconds; `BRIDGE_ARGS.max_wall_seconds` can extend it.

Outside Unreal, `python Tools/test_native_playable.py --list` prints the plan with `status: not_run`. It does not exercise gameplay.

## The 35 passing observations

- Native GameMode/GameState/player classes; exactly 16 uniquely assigned roster slots in the eight-position distribution; seven balls with the Snitch still scheduled and Snipe active.
- Frozen lobby clock; host Chaser selection; live clock start; rejected live role changes; host stoppage with frozen clock; host team/Ranger selection; resumed clock.
- Native CharacterMovement flight through the open crown; capsule-inset chase ceiling; side envelope above the physical net.
- Side-net ball restitution and trampoline rebound. Free and carried No Crown transitions must kill/release only the affected ball and return it below the roofline. The carried case first obtains possession through the actual input path.
- A Quark crossing a large hoop and a reverse Quaffle crossing award nothing; a rim strike rebounds without points; forward whole-ball Quaffle and Quark goals produce the observed 13- and 37-point deltas for the correct teams. Rejected crossing fixtures also check that they reached the relevant side of the goal plane.
- Chaser/Snipe, Hurleyback/Quaffle, and Scout/Quaffle ineligibility; actual Hurleyback/Bludger possession.
- Observable Snipe progress before one second; release and range-break resets; one continuous eligible hold awards 69 and starts the 180-second timeout.

Detailed observations, score deltas, positions, velocities, roster slots, engine version, DLL timestamp/size, world path, and input events are written into the report. `TEST_NAMES` in the script is the canonical case list.

## Fixture boundaries

`BBRiderCharacter::DevelopmentRequestAction(Action, Value)` submits the same action/RPC route as normal input. Actions are pickup `0`, throw `1`, role `2`, team `3`, ready/resume `4`, and stoppage `5`. `DevelopmentSetInteraction(bool)` enters the ordinary hold/release route while keeping a physical E-key reconciliation from cancelling the fixture. Their return values mean the request was submitted, not that the rule engine accepted it. Both require a non-Shipping PIE world and a locally controlled rider with a PlayerController. Cleanup explicitly releases the held interaction.

`BBBall::DevelopmentSetFlightFixture(Location, Velocity)` only sets a free ball's transform, prior position, and flight velocity, then requests a replication update. It rejects Shipping, non-PIE, non-authority, held-ball, and nonfinite-vector calls. It does not alter holder, activation, cooldown, capture progress, score, clock, or rules. It is an ordinary callable method, not a server RPC; the test must already be running on the authority world. The guard exists in C++, independently of the `DevelopmentOnly` metadata.

`BBBall::GetFlightVelocity()` provides the read-only authority simulation diagnostic used by the rebound assertions. It does not describe the smoothed client visual velocity. Other state observations use exposed read-only properties. CharacterMovement and capsule components are obtained through reflected component lookup.

The runner never calls `set_editor_property` to inject gameplay state. It disables actor and CharacterMovement component ticks on CPU PIE copies and parks those copies beyond interaction range. MatchState AI decisions remain active; this isolation prevents CPU movement/pickups from disturbing the narrow observations and is reapplied after position swaps. Unused ball ticks are disabled. All these changes disappear when the owned PIE world ends.

Flight cases feed `AddMovementInput` into the actual CharacterMovement component. Capture cases move the player beside the moving Snipe each frame to isolate the hold/range/eligibility contract. This is not an automated demonstration that a human can chase it comfortably. Role changes and pause/resume use native input requests rather than rewriting roster or ownership fields.

## Required follow-up evidence

This suite establishes only the listed native behavior in one authority PIE world. The separately passing network suite covers specific client RPC and replication checks. Neither suite establishes latency/jitter behavior, join/leave replacement, or dedicated-server host selection. Real server/client processes still need the gameplay scenarios in `Docs/networking.md`, beyond the passing connection smoke.

Timed Snitch release/capture, overtime/Donnybrook presentation, autonomous full-roster play, physical keyboard/mouse bindings, HUD feedback, packaged native startup/rendering, sustained frame time, sound, and visual quality require their own runtime checks. Regulation schedules the Snitch after 22 live minutes; native `-Practice` schedules it after one live minute. The short PIE suite verifies its initial scheduled state, not its later release or capture.

Full regulation remains incomplete, including penalty-shot execution, wand gameplay, and complete officiating/adjudication flows. The portable rules suite covers additional adjudication semantics but cannot certify their integration with the Unreal scene. No full multiplayer, complete ruleset, or performance claim follows from this milestone.
