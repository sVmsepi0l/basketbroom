# Native gameplay validation

`Tools/test_native_playable.py` is an asynchronous, single-world Unreal Engine 5.8 PIE integration suite for `BBGameMode`, `BBMatchState`, `BBRiderCharacter`, and `BBBall`. It is separate from the playable training Blueprint tests and the portable C++ rules tests.

**Current status, 2026-09-12: 35/35 PASSED.** The compiled native module loaded in Unreal Engine 5.8.1 and the complete single-world PIE suite passed in 13.344 seconds after the combined rider, wing and admission/disconnect build: 35 passed, 0 failed, 0 not run. The six-suite combined run passed 96 checks, including the separately scoped admission, disconnect, networking, openings and Snitch suites below. The harness observes state transitions and spaces queued requests to respect the native input throttle. The report is `.local/native-playable-test-results.json`, with the observed native GameMode, GameState, and pawn classes and the `UEDPIE_0_BB_Regulation` world recorded. The regulation map is staged and enabled in the project.

Native Editor compilation and Win64 Development game compilation, cooking, staging, packaging, and archiving also succeeded. The local toolchain is Visual Studio 2026 with MSVC 14.51.36257, Windows SDK 26100, and the .NET Framework 4.8 SDK. `.local/latest-package.json` records a completed package with `NativeRuntime: true`. A headless native package loaded the regulation map with BBGameMode without errors. All seventeen same-process networking checks passed, and two packaged processes completed a loopback join and map load; see `networking.md` for the narrower scope of each result. The separate physical-key and packaged rendering observations are recorded below.

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

## Practice Snitch and rematch evidence

`Tools/test_native_snitch.py` passed **19/19 checks in 28.610 seconds on 2026-09-12**, recorded in `.local/native-snitch-test-results.json`. It verified the native practice configuration, sixteen-slot roster, seven balls, host Scout selection, and live clock. The Snitch was inactive at 59.706 live seconds and first observed active at 60.040; release awarded no points. An eligible held interaction produced partial progress, release reset it, and a fresh continuous hold awarded exactly 150 points. The match entered `CERTIFYING RESULT` and certified the catching team as the final winner after two game seconds.

The runner uses the live EditorEngine's public editable `InEditorGameURLOptions` to append `?Practice=1` and requires observed `bPractice` before proceeding. UE5.8's `AdditionalServerGameOptions` only feeds separate-process launch, so it is unsuitable for this in-process fixture. The successful run restored the exact original editor URL and managed play settings, restored the world's time dilation, and ended the owned PIE session. No score, clock, rule state, capture progress, or activation was written.

Only the disposable world's time changes: 8x toward release, 1x across the 60-second boundary, 0.1x while following the actual moving Snitch for capture, then 1x for review. The maximum observed capture step was 0.0333 game seconds; the runner excludes catch observations if a step exceeds 0.2. Physical piloting, normal-speed human chase difficulty, the 22-minute regulation release, the 300-point overtime catch, and network capture remain unvalidated by this fixture.

After the actual certified `FINAL`, the normal host ready action started a practice rematch in live quarter one, with winner reset to -1. Scores changed from 150–0 to 0–0; the next observed clock was 0.333 live seconds with 179.667 seconds left. Native world, GameMode, MatchState, controller, all sixteen riders, seven balls, roster slots, teams, and selected roles were retained. Held, stun, possession, and capture flags were clear, and the Snitch was scheduled again. An ordinary held-input request before Enter made the held-state reset observable; the fixture did not seed a stun. CPU/ball isolation was reapplied after native kickoff/rematch repositioning.

## Opening-layout evidence

`Tools/test_native_openings.py` passed **11/11 checks in 47.016 seconds on 2026-09-12**, recorded in `.local/native-opening-test-results.json`. Two actual Quark goals created a 37–37 tie. With 20x dilation in the disposable PIE world, four three-minute practice quarters and 120-second overtime elapsed through the native rules engine, carrying that score into Donnybrook. The script did not write scores, clocks, or phases.

The observed initial/quarter openings put whole rider capsules behind the required lines and equipment on neutral marks. Ordinary official stoppage/resume preserved field positions. Overtime reopened with all seven balls; Donnybrook placed riders at the goal lines with only the two Quarks and Snipe active. Cleanup restored the URL/play settings and time dilation and ended PIE. These checks establish opening geometry and activity across real practice transitions, not false-start adjudication, autonomous tactics, full-length regulation timing, or remote replication.

## Bludger evidence

`Tools/test_native_bludgers.py` passed **9/9 checks in 171.671 seconds on 2026-09-12**, recorded in `.local/native-bludger-test-results.json`. The isolated 0.15x PIE fixture uses ordinary inputs and actual native ball/rule ticks. A short self-toss retained accumulated individual control; cumulative flight beyond ten feet and a short floor contact reset it. An opponent could be hit during pickup lockout, the thrower was protected during initial launch clearance, and a returning ball could hit that thrower after clearance expired.

Dead-ball restarts selected the nearest eligible opposing Hurleyback, used the lower roster slot on equal distance, and skipped a stunned nearer receiver. Scores remained unchanged. The fixture restored time dilation. It does not establish human contestability judgments, autonomous match behavior, remote transport, packaged behavior, or Hurley striking mechanics.

## No Crown evidence

`Tools/test_native_crown.py` passed **10/10 checks in 80.657 seconds on 2026-09-12**. Actual carried and released roof exits preserved the responsible rider after launch clearance and a net bank. Unknown exits returned without punishment; neutral official restarts cleared stale release responsibility. The affected ball returned while another ball and the live clock continued, and the penalty remained due until its restoration at a later stoppage. Scoring-ball restoration selected an eligible opposing Chaser; Bludger restoration selected an eligible opposing Hurleyback.

`Tools/test_native_crown_edges.py` subsequently passed **4/4 checks in 52.812 seconds**, including the latest clearance/spacing changes. With all eligible opponents physically stunned, the reserved ball remained dead. After one receiver recovered, its whole carried Quark stayed inside the near end net. A high opponent was moved 500 cm inward to establish 450 cm horizontal separation while retaining altitude, downward aim, custody of another legal Quark, and no additional Crown foul. These disposable PIE fixtures use native inputs and ball/rule ticks, without assigning penalties or custody. Their 0.2x time dilation was restored. The edge fixture suspends its owned controllers' look updates to establish stable aim; it does not override subsequent native spacing or rotation changes.

Reports are `.local/native-crown-test-results.json` and `.local/native-crown-edge-test-results.json`. These observations do not establish intent-based Dead-Roof Delay judgments, remote replication, penalty shots, or complete officiating.

## Native audio evidence

`Tools/test_native_audio.py` passed **11/11 checks in 4.781 seconds on 2026-09-10**, recorded in `.local/native-audio-test-results.json`. It loaded original SoundWave assets, observed pickup/throw/goal/Snipe-catch events starting the expected audio components, checked that unchanged state and timeout did not repeat cues, and observed component cleanup after cues completed. These checks exercise native event integration. They do not establish speaker output, subjective mix quality, packaged audio cooking, remote-client timing, or bounce feedback.

## Required follow-up evidence

The gameplay and chase suites establish only the listed native behavior in one authority PIE world. The separately passing network suite covers specific client RPC and replication checks. Admission and disconnect now have seven passing checks each, described in `networking.md`. These suites do not establish latency/jitter behavior, internet reconnection or dedicated-server host selection. Real server/client processes still need the gameplay scenarios in `Docs/networking.md`, beyond the passing connection smoke.

The September 12 package `Development-20260912-092259-936` includes the combined native source and corrected wing assets. Physical **6** selected Scout, **T** selected Copper, and **Enter** started live practice. **Tab** opened and closed the position guide during play. **P** entered stoppage at 2:15; the clock stayed at 2:15 through a position request, and physical **Enter** resumed play with subsequent clock advancement to 1:56 and natural Snitch release. The inspection used visible Windows keyboard input, without injected game state; `.local/packaged-controls-20260912.json` records its scope. A Hurleyback request was correctly refused while target CPU slots were restricted, but the old message blamed another player. The subsequent source revision changes that message only to say the position is occupied or currently restricted. Physical Enter at a certified final result and physical chase capture remain unverified.

Actual 1600x900 native PIE captures on 2026-09-12 show the Hurley's wood/leather/ivory materials, its smaller cockpit presentation below the equipment cards, and the staggered opening formation leaving the forward view clear. The Scout capture has no Hurley, and the live Scout capture shows the regulation clock, equipment states and chase guidance. See `Screenshots/native-hurleyback.png`, `native-scout.png`, and `native-flight.png`. Read-only equipment visibility and owner-filter inspection also passed. These images establish the observed framing and material fix, not sustained performance, remote equipment visibility, or final art quality.

The packaged inspection also showed the updated seated riders, team materials, venue and chase wings in live play. Phase presentation beyond the opening geometry, autonomous full-roster play, remaining physical bindings and sustained frame time still require their own checks. The practice suites do not certify every regulation phase or a complete match. `Tools/native_play_session.py` selects a position through ordinary queued input at lobby/stoppage and captures after actual game frames. The Hurley is an original provisional prop, about 103 cm overall with a shallow 36 cm-wide head. The current oversized Bludger does not physically fit; no striking, pocket-release or dimension-certification result is claimed.

Full regulation remains incomplete, including penalty-shot execution, wand gameplay, and complete officiating/adjudication flows. The portable rules suite covers additional adjudication semantics but cannot certify their integration with the Unreal scene. No full multiplayer, complete ruleset, or performance claim follows from this milestone.
