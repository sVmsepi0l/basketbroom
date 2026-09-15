# native gameplay validation

the current [sprint 3 handoff](sprint-3-spells-graphics.md#validation-and-package-handoff) records the september 14 spell, free-shot, equipment and package checks. the dated milestones below retain their original build scope.

> **historical roof evidence:** dated open-crown and no crown checks below describe earlier builds and were superseded by the 2026/09/14 [closed pyramid-net amendment](pyramid-net.md). their original results are preserved. the crown-specific test entry points are now retired and return `not_run`; use the new roof tests for current behavior.

`Tools/test_native_playable.py` is an asynchronous, single-world unreal engine 5.8 pie integration suite for `bbgamemode`, `bbmatchstate`, `bbridercharacter`, and `BBBall`. it is separate from the playable training blueprint tests and the portable c++ rules tests.

**current core-suite status, 2026/09/12: 35/35 PASSED.** the compiled native module loaded in unreal engine 5.8.1 and the latest bb-0 regression run passed in 12.969 seconds: 35 passed, 0 failed, 0 not run. the earlier six-suite combined run passed 96 checks, including the separately scoped admission, disconnect, networking, openings and snitch suites below. the harness observes state transitions and spaces queued requests to respect the native input throttle. the report is `.local/native-playable-test-results.json`, with the observed native gamemode, gamestate, and pawn classes and the `uedpie_0_bb_regulation` world recorded. the regulation map is staged and enabled in the project.

the later [partial wandplay milestone](native-wandplay-validation.md) totals **212 passing checks: 130 portable and 82 native**. its native count includes this core regression, 17 general network checks and 30 new regulation/Bloodbroom/spell-network checks. the linked receipt identifies each run and its limits; it separately tracks the new standalone package/UI outcome. historical package observations below identify their own earlier builds.

native editor compilation and win64 development game compilation, cooking, staging, packaging, and archiving also succeeded. the local toolchain is visual studio 2026 with msvc 14.51.36257, windows sdk 26100, and the .NET framework 4.8 SDK. `.local/latest-package.json` records a completed package with `NativeRuntime: true`. a headless native package loaded the regulation map with bbgamemode without errors. all seventeen same-process networking checks passed. two packaged processes also passed physical loopback role/authority, result/rematch, stoppage and basic departure checks; see [networking.md](networking.md) for each scope. the separate physical-key and packaged rendering observations are recorded below.

## repeat the suite

1. complete the supported MSVC/Windows sdk setup described in the repository readme, then run `Build-Native.ps1 -target editor` successfully. close and reopen the editor so it loads the resulting native DLL.
2. run `Tools/stage_regulation.py` in the UE5.8 editor. it derives `/Basketbroom/Maps/BB_Regulation` from the existing arena and assigns the native GameMode. select that map and stop any existing pie session.
3. run `py C:/Git/basketbroom/Tools/test_native_playable.py` in the unreal console, or submit that script through the existing `Tools/editor_bridge.py` mailbox using a unique request ID. no other basketbroom integration suite should be active. avoid keyboard/mouse gameplay input until this runner finishes.
4. read `.local/native-playable-test-results.json`. the console/mailbox result `started` only means the slate callback was registered. the json report's final `status` is the result.

the suite starts its own fresh pie session and always ends it. it changes only transient pie copies and does not save a map. it declines an existing session, a missing native DLL/class/fixture bridge, or an unsuitable engine with `not_run`. a missing native world after 30 seconds is also `not_run`. Exceptions/timeouts are `error`, failed observations are `failed`, and `passed` requires all planned cases to have run and passed. remaining cases retain `not_run` after an interrupted run. the default wall-time limit is 240 seconds; `BRIDGE_ARGS.max_wall_seconds` can extend it.

outside unreal, `python Tools/test_native_playable.py --list` prints the plan with `status: not_run`. it does not exercise gameplay.

## the 35 passing observations

- native GameMode/GameState/player classes; exactly 16 uniquely assigned roster slots in the eight-position distribution; seven balls with the snitch still scheduled and snipe active.
- frozen lobby clock; host chaser selection; live clock start; rejected live role changes; host stoppage with frozen clock; host team/Ranger selection; resumed clock.
- native charactermovement flight through the open crown; capsule-inset chase ceiling; side envelope above the physical net.
- side-net ball restitution and trampoline rebound. free and carried no crown transitions must kill/release only the affected ball and return it below the roofline. the carried case first obtains possession through the actual input path.
- a quark crossing a large hoop and a reverse quaffle crossing award nothing; a rim strike rebounds without points; forward whole-ball quaffle and quark goals produce the observed 13- and 37-point deltas for the correct teams. rejected crossing fixtures also check that they reached the relevant side of the goal plane.
- Chaser/Snipe, Hurleyback/Quaffle, and Scout/Quaffle ineligibility; actual Hurleyback/Bludger possession.
- observable snipe progress before one second; release and range-break resets; one continuous eligible hold awards 69 and starts the 180-second timeout.

detailed observations, score deltas, positions, velocities, roster slots, engine version, dll timestamp/size, world path, and input events are written into the report. `test_names` in the script is the canonical case list.

## fixture boundaries

`BBRiderCharacter::DevelopmentRequestAction(Action, value)` submits the same action/RPC route as normal input. actions are pickup `0`, throw `1`, role `2`, team `3`, ready/resume `4`, and stoppage `5`. `developmentsetinteraction(bool)` enters the ordinary hold/release route while keeping a physical e-key reconciliation from cancelling the fixture. their return values mean the request was submitted, not that the rule engine accepted it. both require a non-shipping pie world and a locally controlled rider with a PlayerController. cleanup explicitly releases the held interaction.

`BBBall::DevelopmentSetFlightFixture(Location, velocity)` only sets a free ball's transform, prior position, and flight velocity, then requests a replication update. it rejects shipping, non-pie, non-authority, held-ball, and nonfinite-vector calls. it does not alter holder, activation, cooldown, capture progress, score, clock, or rules. it is an ordinary callable method, not a server rpc; the test must already be running on the authority world. the guard exists in c++, independently of the `developmentonly` metadata.

`BBBall::GetFlightVelocity()` provides the read-only authority simulation diagnostic used by the rebound assertions. it does not describe the smoothed client visual velocity. other state observations use exposed read-only properties. charactermovement and capsule components are obtained through reflected component lookup.

the runner never calls `set_editor_property` to inject gameplay state. it disables actor and charactermovement component ticks on cpu pie copies and parks those copies beyond interaction range. matchstate ai decisions remain active; this isolation prevents cpu movement/pickups from disturbing the narrow observations and is reapplied after position swaps. unused ball ticks are disabled. all these changes disappear when the owned pie world ends.

flight cases feed `addmovementinput` into the actual charactermovement component. capture cases move the player beside the moving snipe each frame to isolate the hold/range/eligibility contract. this is not an automated demonstration that a human can chase it comfortably. role changes and pause/resume use native input requests rather than rewriting roster or ownership fields.

## practice snitch and rematch evidence

`Tools/test_native_snitch.py` passed **19/19 checks in 28.610 seconds on 2026/09/12**, recorded in `.local/native-snitch-test-results.json`. it verified the native practice configuration, sixteen-slot roster, seven balls, host scout selection, and live clock. the snitch was inactive at 59.706 live seconds and first observed active at 60.040; release awarded no points. an eligible held interaction produced partial progress, release reset it, and a fresh continuous hold awarded exactly 150 points. the match entered `certifying result` and certified the catching team as the final winner after two game seconds.

the runner uses the live editorengine's public editable `ineditorgameurloptions` to append `?practice=1` and requires observed `bpractice` before proceeding. UE5.8's `additionalservergameoptions` only feeds separate-process launch, so it is unsuitable for this in-process fixture. the successful run restored the exact original editor url and managed play settings, restored the world's time dilation, and ended the owned pie session. no score, clock, rule state, capture progress, or activation was written.

only the disposable world's time changes: 8x toward release, 1x across the 60-second boundary, 0.1x while following the actual moving snitch for capture, then 1x for review. the maximum observed capture step was 0.0335 game seconds; the runner excludes catch observations if a step exceeds 0.2. physical piloting, normal-speed human chase difficulty, the 22-minute regulation release, the 300-point overtime catch, and network capture remain unvalidated by this fixture.

after the actual certified `final`, the normal host ready action started a practice rematch in live quarter one, with winner reset to -1. scores changed from 150–0 to 0–0; the next observed clock was 0.333 live seconds with 179.667 seconds left. native world, gamemode, matchstate, controller, all sixteen riders, seven balls, roster slots, teams, and selected roles were retained. held, stun, possession, and capture flags were clear, and the snitch was scheduled again. an ordinary held-input request before enter made the held-state reset observable; the fixture did not seed a stun. CPU/ball isolation was reapplied after native kickoff/rematch repositioning.

## opening-layout evidence

`Tools/test_native_openings.py` passed **11/11 checks in 47.016 seconds on 2026/09/12**, recorded in `.local/native-opening-test-results.json`. two actual quark goals created a 37–37 tie. with 20x dilation in the disposable pie world, four three-minute practice quarters and 120-second overtime elapsed through the native rules engine, carrying that score into Donnybrook. the script did not write scores, clocks, or phases.

the observed initial/quarter openings put whole rider capsules behind the required lines and equipment on neutral marks. ordinary official stoppage/resume preserved field positions. overtime reopened with all seven balls; donnybrook placed riders at the goal lines with only the two quarks and snipe active. cleanup restored the URL/play settings and time dilation and ended PIE. these checks establish opening geometry and activity across real practice transitions, not false-start adjudication, autonomous tactics, full-length regulation timing, or remote replication.

## bludger evidence

`Tools/test_native_bludgers.py` passed **9/9 checks in 171.671 seconds on 2026/09/12**, recorded in `.local/native-bludger-test-results.json`. the isolated 0.15x pie fixture uses ordinary inputs and actual native ball/rule ticks. a short self-toss retained accumulated individual control; cumulative flight beyond ten feet and a short floor contact reset it. an opponent could be hit during pickup lockout, the thrower was protected during initial launch clearance, and a returning ball could hit that thrower after clearance expired.

dead-ball restarts selected the nearest eligible opposing hurleyback, used the lower roster slot on equal distance, and skipped a stunned nearer receiver. scores remained unchanged. the fixture restored time dilation. it does not establish human contestability judgments, autonomous match behavior, remote transport, packaged behavior, or hurley striking mechanics.

## no crown evidence

`Tools/test_native_crown.py` passed **10/10 checks in 80.657 seconds on 2026/09/12**. actual carried and released roof exits preserved the responsible rider after launch clearance and a net bank. unknown exits returned without punishment; neutral official restarts cleared stale release responsibility. the affected ball returned while another ball and the live clock continued, and the penalty remained due until its restoration at a later stoppage. scoring-ball restoration selected an eligible opposing chaser; bludger restoration selected an eligible opposing Hurleyback.

`Tools/test_native_crown_edges.py` subsequently passed **4/4 checks in 52.812 seconds**, including the latest clearance/spacing changes. with all eligible opponents physically stunned, the reserved ball remained dead. after one receiver recovered, its whole carried quark stayed inside the near end net. a high opponent was moved 500 cm inward to establish 450 cm horizontal separation while retaining altitude, downward aim, custody of another legal quark, and no additional crown foul. these disposable pie fixtures use native inputs and ball/rule ticks, without assigning penalties or custody. their 0.2x time dilation was restored. the edge fixture suspends its owned controllers' look updates to establish stable aim; it does not override subsequent native spacing or rotation changes.

reports are `.local/native-crown-test-results.json` and `.local/native-crown-edge-test-results.json`. these observations do not establish intent-based dead-roof delay judgments, remote replication, penalty shots, or complete officiating.

## native audio evidence

`Tools/test_native_audio.py` passed **11/11 checks in 4.781 seconds on 2026/09/10**, recorded in `.local/native-audio-test-results.json`. it loaded original soundwave assets, observed pickup/throw/goal/Snipe-catch events starting the expected audio components, checked that unchanged state and timeout did not repeat cues, and observed component cleanup after cues completed. these checks exercise native event integration. they do not establish speaker output, subjective mix quality, packaged audio cooking, remote-client timing, or bounce feedback.

## packaged observations and remaining validation

the gameplay and chase suites establish only the listed native behavior in one authority pie world. the separately passing network suite covers specific client rpc and replication checks. admission and disconnect now have seven passing checks each, described in [networking.md](networking.md). the physical packaged pair below adds real process-to-process gameplay evidence. Latency/jitter, internet reconnection, dedicated-server host selection and the remaining human ball-contest scenarios still need separate validation.

the september 12 package `development-20260912-092259-936` includes the combined native source and corrected wing assets. physical **6** selected scout, **t** selected copper, and **enter** started live practice. **tab** opened and closed the position guide during play. **p** entered stoppage at 2:15; the clock stayed at 2:15 through a position request, and physical **enter** resumed play with subsequent clock advancement to 1:56 and natural snitch release. the inspection used visible windows keyboard input, without injected game state; `.local/packaged-controls-20260912.json` records its scope. a hurleyback request was correctly refused while target cpu slots were restricted, but the old message blamed another player. the subsequent package changes that message only to say the position is occupied or currently restricted.

that final package, **`development-20260912-093008-251`**, then passed a physical two-process practice pass on loopback port **18780**, recorded in `.local/packaged-multiplayer-controls-20260912.json`. client **5** selected Copper/Hurleyback and the host received its role message. client **enter** could not start the lobby; host **enter** started it and the client received LIVE/equipment/score state. client **p** did not stop live play. both views showed a certified copper victory, **teal 113–copper 417**, at quarter-one clock **01:45**. client **enter** could not rematch; after host **enter**, the host view showed **0–0, 03:00, LIVE**. the client's initial reset frame was not directly observed; its next snapshot matched the later rematch stoppage described below. this is actual physical host enter-at-final evidence.

host **p** stopped that rematch at **02:54, teal 87–copper 0**; the client matched status, scores and clock while retaining Copper/Hurleyback. after client **alt+f4**, the host remained at **02:54, 87–0**. host **enter** resumed it and the observed clock advanced to **02:47, teal 87–copper 69**, before host **Alt+F4**. the two logs in `.local/Multiplayer/20260912-093603-884` show normal viewport-close exits at **09:43:14 client** and **09:43:44 host** local time, host-side client cleanup, and no engine/network errors or network warnings. the gameplay observations came from visible ui and physical keys, without injected state.

this packaged pass covers the listed two-process role, authority, shared result/rematch, stoppage and basic departure behavior. it does not cover manual chase capture, held-ball departure, remote-machine play, latency/load, full regulation or sixteen humans. held custody and historical-remedy behavior on departure remain separately tested in disposable pie fixtures.

actual 1600x900 native pie captures on 2026/09/12 show the hurley's wood/leather/ivory materials, its smaller cockpit presentation below the equipment cards, and the staggered opening formation leaving the forward view clear. the scout capture has no hurley, and the live scout capture shows the regulation clock, equipment states and chase guidance. see `Screenshots/native-hurleyback.png`, `native-scout.png`, and `native-flight.png`. read-only equipment visibility and owner-filter inspection also passed. these images establish the observed framing and material fix, not sustained performance, remote equipment visibility, or final art quality.

the packaged inspection also showed the updated seated riders, team materials, venue and chase wings in live play. phase presentation beyond the opening geometry, autonomous full-roster play, remaining physical bindings and sustained frame time still require their own checks. the practice suites do not certify every regulation phase or a complete match. `Tools/native_play_session.py` selects a position through ordinary queued input at lobby/stoppage and captures after actual game frames. the hurley is an original provisional prop, about 103 cm overall with a shallow 36 cm-wide head. the current oversized bludger does not physically fit; no striking, pocket-release or dimension-certification result is claimed.

full regulation remains incomplete, including full spell parity and final officiating/adjudication flows. current source implements [23 sporting spell adapters with eight contextual actions pending](native-sport-spells.md), alongside [moderate free shots and serious penalty shots](native-penalty-shots.md). these changes have their own validation scope; the dated receipts above remain evidence of their named builds. portable rule coverage cannot certify every remaining unreal integration. no complete ruleset, hogwarts legacy multiplayer or sustained-performance claim follows from these milestones.
